import re
from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings

from analytics.models import TraderProfile
from chat.models import Conversation, Message
from trades.models import Trade, TradeFile


PASSWORD = "Kestrel-Vault-72"


def link_parts(message):
    """The uid and token out of whichever link the mail carries."""
    found = re.search(r"/authentication/(?:verify|reset)/([^/\s]+)/([^/\s]+)", message.body)
    return (found.group(1), found.group(2)) if found else (None, None)



class SignUpBase(APITestCase):
    """Registration, and the click on the mailed link that follows it."""

    def setUp(self):
        mail.outbox = []
        self.user_data = {"username": "omer", "password": PASSWORD, "email": "omer@larson.com"}


    def register(self, **overrides):
        return self.client.post("/authentication/register/", {**self.user_data, **overrides})


    def verify(self):
        uid, token = link_parts(mail.outbox[-1])
        return self.client.post("/authentication/verify/", {"uid": uid, "token": token})


    def sign_in(self, password = PASSWORD):
        return self.client.post("/authentication/login/",
                                {"username": "omer", "password": password})


    def signed_in(self):
        """A verified account, logged in, with the tokens returned."""
        self.register()
        self.verify()
        tokens = self.sign_in().data
        self.client.credentials(HTTP_AUTHORIZATION = f"Bearer {tokens['access']}")
        return tokens



# ------------------------- REGISTRATION TESTS START ------------------------- #

class RegistrationTests(SignUpBase):

    def test_register_creates_user(self):
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username = "omer").exists())


    def test_register_rejects_duplicate_username(self):
        self.register()
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(username = "omer").count(), 1)


    def test_the_account_starts_unverified(self):
        self.register()

        self.assertFalse(User.objects.get(username = "omer").is_active)


    def test_registering_sends_one_mail_to_the_address_given(self):
        self.register()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["omer@larson.com"])


    # ------------- THE VALIDATORS THAT WERE CONFIGURED BUT NEVER RAN:
    def test_a_short_password_is_refused(self):
        response = self.register(password = "aA1!")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("8", response.data["error"])
        self.assertFalse(User.objects.filter(username = "omer").exists())


    def test_a_common_password_is_refused(self):
        # The one the whole test suite used to sign up with, which is the point: it was
        # accepted for the entire life of the project.
        response = self.register(password = "Aa123456")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username = "omer").exists())


    def test_an_all_numeric_password_is_refused(self):
        response = self.register(password = "84027395617")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_a_password_that_is_the_username_is_refused(self):
        response = self.register(username = "kestrelvault", password = "kestrelvault")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_the_refusal_is_in_hebrew(self):
        response = self.register(password = "aA1!")

        # Django answers in English; every message this product shows is in Hebrew.
        self.assertRegex(response.data["error"], r"[֐-׿]")

# ------------------------- REGISTRATION TESTS END ------------------------- #



# ------------------------- VERIFICATION TESTS START ------------------------- #

class EmailVerificationTests(SignUpBase):

    def test_the_link_activates_the_account(self):
        self.register()
        response = self.verify()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.get(username = "omer").is_active)


    def test_a_tampered_token_is_refused(self):
        self.register()
        uid, _ = link_parts(mail.outbox[-1])

        response = self.client.post("/authentication/verify/", {"uid": uid, "token": "not-a-token"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.get(username = "omer").is_active)


    def test_an_unknown_uid_is_refused_without_blowing_up(self):
        response = self.client.post("/authentication/verify/", {"uid": "!!!", "token": "x"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_using_the_link_twice_still_reads_as_success(self):
        self.register()
        self.verify()

        # The token is dead - `is_active` is inside its hash - but the trader did what he was
        # asked and telling him it failed would send him hunting for a second mail.
        response = self.verify()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("success", response.data)


    def test_a_resend_delivers_a_working_link(self):
        self.register()
        mail.outbox = []

        self.client.post("/authentication/verify/resend/", {"email": "omer@larson.com"})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.verify().status_code, status.HTTP_200_OK)


    def test_a_resend_for_an_unknown_address_says_the_same_thing(self):
        response = self.client.post("/authentication/verify/resend/", {"email": "nobody@larson.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)


    # ------------- LOGGING IN BEFORE VERIFYING:
    def test_login_before_verifying_says_so_instead_of_wrong_password(self):
        self.register()
        response = self.sign_in()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.data["needs_verification"])


    def test_a_wrong_password_on_an_unverified_account_is_still_just_wrong(self):
        self.register()
        response = self.sign_in(password = "Some-Other-Pass-91")

        # Otherwise this endpoint would confirm which addresses are registered to anyone who
        # guesses a username - the answer must only follow a correct password.
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_login_works_once_verified(self):
        self.register()
        self.verify()
        response = self.sign_in()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

# ------------------------- VERIFICATION TESTS END ------------------------- #


# ------------------------- WHAT THE MAIL LOOKS LIKE TESTS START ------------------------- #

class MailShapeTests(SignUpBase):
    """
    The message itself, rather than the flow that sends it.

    Everything here is about the difference between "a mail went out" and "a mail arrived
    looking like the product sent it" - which the flow tests above cannot tell apart.
    """

    def sent(self):
        self.register()
        return mail.outbox[-1]


    def test_it_goes_out_as_text_and_as_html(self):
        message = self.sent()

        # Only-HTML looks broken in a text client and scores worse with spam filters;
        # only-text does not look like it came from the product it claims to come from.
        self.assertEqual(len(message.alternatives), 1)
        self.assertEqual(message.alternatives[0][1], "text/html")
        self.assertIn("Larson", message.body)


    def test_the_mark_rides_inside_the_html_and_not_beside_it(self):
        built = self.sent().message()

        shape = []
        def walk(part):
            shape.append(part.get_content_type())
            if part.is_multipart():
                for sub in part.get_payload():
                    walk(sub)
        walk(built)

        # Attached at the top level the picture is a file the reader is offered rather than
        # something the message draws, and clients show it as a paperclip.
        self.assertEqual(shape, ["multipart/alternative", "text/plain",
                                 "multipart/related", "text/html", "image/png"])


    def test_the_mark_carries_the_id_the_html_points_at(self):
        built = self.sent().message()
        image = built.get_payload()[1].get_payload()[1]

        self.assertEqual(image.get("Content-ID"), "<larson>")
        self.assertIn('src="cid:larson"', self.sent().alternatives[0][0])


    def test_it_renders_the_way_the_smtp_backend_asks_for_it(self):
        # **The regression this class exists for.** The SMTP backend calls `message(policy=…)`
        # and the in-memory backend used by every other test calls it with no arguments, so an
        # override that fits only one of them passes the whole suite and fails on the first
        # real send. It did exactly that.
        from email import policy

        built = self.sent().message(policy = policy.SMTP)
        self.assertTrue(built.is_multipart())


    def test_the_html_says_everything_the_picture_would(self):
        html = self.sent().alternatives[0][0]

        # Most clients block images on a first message from an unknown sender, so nothing may
        # depend on the mark being drawn.
        self.assertIn("LARSON", html)
        self.assertIn("אישור הכתובת", html)
        self.assertIn("/authentication/verify/", html)


    def test_the_direction_survives_gmail_throwing_the_document_away(self):
        """
        **The regression this replaced a weaker test for.**

        The old assertion looked for `dir="rtl"` anywhere in the document, and it passed on
        the `<html>` tag - which Gmail deletes. It drops the content into a container of its
        own, the paragraphs are then laid out left-to-right, and the Hebrew runs inside them
        come out in the wrong order. The words are all still there, which is why it reads as
        scrambled text rather than as a missing attribute.
        """
        html = self.sent().alternatives[0][0]

        # What Gmail keeps: everything between <body> and </body>, minus the tags themselves.
        kept = html.split("<body", 1)[1].split(">", 1)[1].rsplit("</body>", 1)[0]

        self.assertIn('dir="rtl"', kept)

        # And not once, at the top: every cell that holds Hebrew has to say it, because the
        # sanitiser is free to keep some elements and drop others.
        self.assertGreaterEqual(kept.count('dir="rtl"'), 6)


    def test_the_hebrew_cells_all_declare_their_direction(self):
        html = self.sent().alternatives[0][0]

        # Any cell carrying Hebrew must carry the direction with it.
        for cell in re.findall(r"<td[^>]*>(?:(?!</td>).)*?[֐-׿](?:(?!</td>).)*?</td>", html, re.S):
            opening = cell.split(">", 1)[0]
            self.assertIn('dir="rtl"', opening, cell[:120])


    def test_the_fallback_url_is_left_to_right(self):
        html = self.sent().alternatives[0][0]

        # A URL dropped into an RTL paragraph has its punctuation reordered, so the address
        # the trader is told to copy is not the address he would copy.
        link = re.search(r"<span([^>]*)>[^<]*http[^<]*</span>", html)
        self.assertIsNotNone(link)
        self.assertIn('dir="ltr"', link.group(1))


    def test_a_missing_mark_does_not_stop_the_mail(self):
        with patch("authentication.mail.MARK", "no/such/file.png"):
            self.register()

        # The mail is written to read correctly with no picture at all, so a missing asset
        # must not turn "confirm your address" into a failure to deliver.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/authentication/verify/", mail.outbox[-1].alternatives[0][0])


    def test_the_security_notice_carries_no_button(self):
        self.signed_in()
        mail.outbox = []
        self.client.post("/authentication/password/change/",
                         {"current_password": PASSWORD, "password": "Marlin-Harbor-58"})

        html = mail.outbox[-1].alternatives[0][0]

        # A button in a security notice is exactly the shape a phishing mail takes, and there
        # is nothing here to confirm in any case.
        self.assertNotIn("</a>", html)

# ------------------------- WHAT THE MAIL LOOKS LIKE TESTS END ------------------------- #




# ------------------------- SESSION TESTS START ------------------------- #

class SessionTests(SignUpBase):

    def test_index_requires_authentication(self):
        response = self.client.get("/authentication/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_index_returns_username_when_logged_in(self):
        self.signed_in()
        response = self.client.get("/authentication/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "omer")


    def test_logout_blacklists_refresh_token(self):
        tokens = self.signed_in()
        response = self.client.post("/authentication/logout/", {"refresh_token": tokens["refresh"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)


    # ------------- THE REFRESH THAT WAS NEVER WIRED UP:
    def test_a_refresh_token_buys_a_new_access_token(self):
        tokens = self.signed_in()

        response = self.client.post("/authentication/refresh/", {"refresh": tokens["refresh"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotEqual(response.data["access"], tokens["access"])


    def test_the_refresh_token_is_rotated(self):
        tokens = self.signed_in()

        fresh = self.client.post("/authentication/refresh/", {"refresh": tokens["refresh"]}).data

        # Rotation is on, so the old one is spent. A refresh token that survived being used
        # would be a 90-day key that leaks once and works forever.
        self.assertIn("refresh", fresh)
        self.assertNotEqual(fresh["refresh"], tokens["refresh"])

        again = self.client.post("/authentication/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(again.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_a_blacklisted_refresh_token_cannot_be_refreshed(self):
        tokens = self.signed_in()
        self.client.post("/authentication/logout/", {"refresh_token": tokens["refresh"]})

        response = self.client.post("/authentication/refresh/", {"refresh": tokens["refresh"]})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

# ------------------------- SESSION TESTS END ------------------------- #



# ------------------------- PASSWORD RESET TESTS START ------------------------- #

class PasswordResetTests(SignUpBase):

    def ask(self, email = "omer@larson.com"):
        mail.outbox = []
        return self.client.post("/authentication/password/forgot/", {"email": email})


    def test_a_registered_address_gets_a_link(self):
        self.signed_in()
        self.ask()

        self.assertEqual(len(mail.outbox), 1)


    def test_an_unknown_address_gets_the_same_answer_and_no_mail(self):
        self.signed_in()
        known = self.ask()
        unknown = self.ask("nobody@larson.com")

        # **Identical, deliberately.** Anything else turns this endpoint into a way to ask,
        # one address at a time, who the customers of a trading product are.
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 0)


    def test_the_link_sets_a_new_password(self):
        self.signed_in()
        self.ask()
        uid, token = link_parts(mail.outbox[0])

        response = self.client.post("/authentication/password/reset/",
                                    {"uid": uid, "token": token, "password": "Marlin-Harbor-58"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials()
        self.assertEqual(self.sign_in("Marlin-Harbor-58").status_code, status.HTTP_200_OK)


    def test_the_old_password_stops_working(self):
        self.signed_in()
        self.ask()
        uid, token = link_parts(mail.outbox[0])
        self.client.post("/authentication/password/reset/",
                         {"uid": uid, "token": token, "password": "Marlin-Harbor-58"})

        self.client.credentials()
        self.assertEqual(self.sign_in(PASSWORD).status_code, status.HTTP_401_UNAUTHORIZED)


    def test_the_link_cannot_be_used_twice(self):
        self.signed_in()
        self.ask()
        uid, token = link_parts(mail.outbox[0])
        self.client.post("/authentication/password/reset/",
                         {"uid": uid, "token": token, "password": "Marlin-Harbor-58"})

        # Django's token hashes the password it was issued against, so setting one spends it.
        again = self.client.post("/authentication/password/reset/",
                                 {"uid": uid, "token": token, "password": "Third-Password-33"})

        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)


    def test_a_weak_new_password_is_refused(self):
        self.signed_in()
        self.ask()
        uid, token = link_parts(mail.outbox[0])

        response = self.client.post("/authentication/password/reset/",
                                    {"uid": uid, "token": token, "password": "123456"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_resetting_ends_every_other_session(self):
        tokens = self.signed_in()
        self.ask()
        uid, token = link_parts(mail.outbox[0])

        self.client.post("/authentication/password/reset/",
                         {"uid": uid, "token": token, "password": "Marlin-Harbor-58"})

        # **This is most of the point of the feature.** Somebody resetting a password often
        # believes another person is inside the account; a session left holding a valid
        # 90-day refresh token would make the reset theatre.
        self.client.credentials()
        response = self.client.post("/authentication/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_an_unverified_account_cannot_reset(self):
        self.register()
        self.ask()

        # Otherwise the reset link is a second door into an address nobody has proved they own.
        self.assertEqual(len(mail.outbox), 0)

# ------------------------- PASSWORD RESET TESTS END ------------------------- #


# ------------------------- CHANGING IT FROM INSIDE TESTS START ------------------------- #

class PasswordChangeTests(SignUpBase):

    def change(self, current = PASSWORD, password = "Marlin-Harbor-58"):
        return self.client.post("/authentication/password/change/",
                                {"current_password": current, "password": password})


    def test_it_requires_being_logged_in(self):
        self.assertEqual(self.change().status_code, status.HTTP_401_UNAUTHORIZED)


    def test_the_current_password_is_required(self):
        self.signed_in()
        response = self.change(current = "not-the-one")

        # An access token left on a shared machine would otherwise be enough to take the
        # account for good, which is exactly the move this is meant to cost something.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_a_weak_new_password_is_refused(self):
        self.signed_in()
        self.assertEqual(self.change(password = "123456").status_code,
                         status.HTTP_400_BAD_REQUEST)


    def test_it_changes_the_password(self):
        self.signed_in()
        self.assertEqual(self.change().status_code, status.HTTP_200_OK)

        self.client.credentials()
        self.assertEqual(self.sign_in("Marlin-Harbor-58").status_code, status.HTTP_200_OK)
        self.assertEqual(self.sign_in(PASSWORD).status_code, status.HTTP_401_UNAUTHORIZED)


    def test_the_caller_stays_logged_in(self):
        self.signed_in()
        fresh = self.change().data

        # Every refresh token was just blacklisted, this caller's included - so a new pair
        # comes back with the answer. **Otherwise changing your own password logs you out**,
        # which teaches people not to change it.
        self.assertIn("access", fresh)
        self.assertIn("refresh", fresh)

        self.client.credentials(HTTP_AUTHORIZATION = f"Bearer {fresh['access']}")
        self.assertEqual(self.client.get("/authentication/").status_code, status.HTTP_200_OK)


    def test_the_other_sessions_are_ended(self):
        elsewhere = self.signed_in()
        self.change()

        self.client.credentials()
        response = self.client.post("/authentication/refresh/", {"refresh": elsewhere["refresh"]})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    # ------------- THE MAIL NOBODY ASKED FOR:
    def test_changing_it_tells_the_owner(self):
        self.signed_in()
        mail.outbox = []

        self.change()

        # **A password change nobody is told about is one an attacker can make in silence**,
        # and the real owner finds out when he can no longer get in.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["omer@larson.com"])


    def test_resetting_it_also_tells_the_owner(self):
        self.signed_in()
        self.client.post("/authentication/password/forgot/", {"email": "omer@larson.com"})
        uid, token = link_parts(mail.outbox[-1])
        mail.outbox = []

        self.client.post("/authentication/password/reset/",
                         {"uid": uid, "token": token, "password": "Marlin-Harbor-58"})

        self.assertEqual(len(mail.outbox), 1)

# ------------------------- CHANGING IT FROM INSIDE TESTS END ------------------------- #





# ------------------------- THE ACCOUNT ITSELF TESTS START ------------------------- #

class AccountDataTests(SignUpBase):

    def populate(self):
        """One of everything the product stores, so the export and the erase have work to do."""
        user = User.objects.get(username = "omer")

        trade_file = TradeFile.objects.create(user = user, original_name = "august.csv",
                                              row_count = 1, imported_count = 1, confirmed = True)
        trade_file.file.save("august.csv", __import__("django").core.files.base.ContentFile(b"x"),
                             save = True)

        Trade.objects.create(user = user, trade_file = trade_file,
                             executed_at = "2026-08-18T10:00:00Z", symbol = "MNQU6",
                             instrument = "NQ", pnl = -120.0, dedup_hash = "abc")

        TraderProfile.objects.create(user = user, profile_text = "מי אתה",
                                     trades_at_generation = 1, score_at_generation = 40)

        conversation = Conversation.objects.create(user = user, title = "שיחה")
        Message.objects.create(conversation = conversation, role = "user", content = "שאלה")
        Message.objects.create(conversation = conversation, role = "assistant", content = "תשובה",
                               verdict = "broken")

        return user, trade_file


    # ------------- EXPORT:
    def test_export_requires_authentication(self):
        response = self.client.get("/authentication/export/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_export_carries_every_part_of_the_record(self):
        self.signed_in()
        self.populate()

        response = self.client.get("/authentication/export/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["account"]["username"], "omer")
        self.assertEqual(len(response.data["resume"]["trades"]), 1)
        self.assertEqual(len(response.data["files"]), 1)
        self.assertIsNotNone(response.data["written_profile"])
        self.assertEqual(len(response.data["conversations"][0]["messages"]), 2)


    def test_export_arrives_as_a_download(self):
        self.signed_in()
        response = self.client.get("/authentication/export/")

        self.assertIn("attachment", response["Content-Disposition"])


    def test_export_never_reaches_into_another_account(self):
        self.signed_in()
        self.populate()

        other = User.objects.create_user(username = "someone", password = PASSWORD,
                                         email = "someone@larson.com")
        Trade.objects.create(user = other, executed_at = "2026-08-18T10:00:00Z",
                             symbol = "ESU6", instrument = "ES", pnl = 50.0, dedup_hash = "zzz")

        response = self.client.get("/authentication/export/")

        self.assertEqual(len(response.data["resume"]["trades"]), 1)
        self.assertEqual(response.data["resume"]["trades"][0]["symbol"], "MNQU6")


    # ------------- DELETION:
    def test_deleting_requires_the_password(self):
        self.signed_in()
        response = self.client.delete("/authentication/account/", {"password": "wrong-one"},
                                      format = "json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(username = "omer").exists())


    def test_deleting_removes_the_account_and_everything_under_it(self):
        self.signed_in()
        self.populate()

        response = self.client.delete("/authentication/account/", {"password": PASSWORD},
                                      format = "json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(username = "omer").exists())
        self.assertEqual(Trade.objects.count(), 0)
        self.assertEqual(TradeFile.objects.count(), 0)
        self.assertEqual(TraderProfile.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)


    def test_deleting_takes_the_uploaded_files_off_the_disk(self):
        self.signed_in()
        _, trade_file = self.populate()
        path = trade_file.file.path

        import os
        self.assertTrue(os.path.exists(path))

        self.client.delete("/authentication/account/", {"password": PASSWORD}, format = "json")

        # Django stopped deleting the bytes behind a FileField when the row goes, so a
        # cascade alone leaves every original export sitting on disk after "delete me".
        self.assertFalse(os.path.exists(path))


    def test_deleting_leaves_other_accounts_alone(self):
        self.signed_in()
        other = User.objects.create_user(username = "someone", password = PASSWORD,
                                         email = "someone@larson.com")
        Trade.objects.create(user = other, executed_at = "2026-08-18T10:00:00Z",
                             symbol = "ESU6", instrument = "ES", pnl = 50.0, dedup_hash = "zzz")

        self.client.delete("/authentication/account/", {"password": PASSWORD}, format = "json")

        self.assertTrue(User.objects.filter(username = "someone").exists())
        self.assertEqual(Trade.objects.filter(user = other).count(), 1)


    def test_the_session_dies_with_the_account(self):
        self.signed_in()
        self.client.delete("/authentication/account/", {"password": PASSWORD}, format = "json")

        # The token is still signed correctly and points at a row that no longer exists.
        response = self.client.get("/authentication/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

# ------------------------- THE ACCOUNT ITSELF TESTS END ------------------------- #



# ------------------------- RATE LIMIT TESTS START ------------------------- #

# The suite runs with the limits off, because the counters outlive a single test and every
# test that signs a user up would eventually trip one. Here they are switched back on, at
# rates small enough to reach in a loop.
LIMITS = {
    "DEFAULT_THROTTLE_RATES": {
        "ai": "2/hour", "ai-day": "2/day", "email": "2/hour",
        "login": "3/hour", "register": "2/hour", "user": "100/hour", "anon": "100/hour",
    }
}


@override_settings(REST_FRAMEWORK = {**LIMITS,
                                     "DEFAULT_AUTHENTICATION_CLASSES": (
                                         "rest_framework_simplejwt.authentication.JWTAuthentication",)})
class ThrottleTests(SignUpBase):

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()


    def tearDown(self):
        from django.core.cache import cache
        cache.clear()


    def test_registration_stops_after_the_limit(self):
        self.register(username = "a", email = "a@larson.com")
        self.register(username = "b", email = "b@larson.com")

        response = self.register(username = "c", email = "c@larson.com")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


    def test_the_password_reset_mail_cannot_be_fired_in_a_loop(self):
        # Without a limit here, "I forgot my password" is a way to make this server deliver
        # mail, on demand and repeatedly, to any address the sender picks.
        for _ in range(2):
            self.client.post("/authentication/password/forgot/", {"email": "omer@larson.com"})

        response = self.client.post("/authentication/password/forgot/",
                                    {"email": "omer@larson.com"})

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


    def test_login_attempts_are_capped(self):
        for _ in range(3):
            self.sign_in(password = "guessing-away")

        response = self.sign_in(password = "guessing-away")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

# ------------------------- RATE LIMIT TESTS END ------------------------- #
