"""
The three messages the product sends, and nothing else.

**Every one goes out twice - as plain text and as HTML - in one multipart message**, and the
client picks. That is not belt and braces: a mail that is only HTML looks broken in a text
client and scores worse with spam filters, and one that is only text does not look like it
came from the product it claims to come from.

**The link is built from `FRONTEND_URL` and never from the request.** A Host header is
attacker-controlled: a reset mail whose URL is assembled from one is how a valid token ends
up delivered to somebody else's server, with the real user's address on the envelope.
"""

import logging
import os

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

from django.conf import settings
from django.utils.html import escape
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives

from .tokens import pack_uid, verification_token


log = logging.getLogger("larson")


HOURS = settings.PASSWORD_RESET_TIMEOUT // 3600

MARK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "larson.png")



# ------------------------- THE SHELL ------------------------- #
# Tables and inline styles, because that is the only layout an email client can be relied on
# to render - there is no flexbox, no grid, no stylesheet and no SVG in an inbox. Larson
# himself is a PNG for the same reason: Gmail strips SVG outright.
#
# **It has to read correctly with the image blocked**, which most clients do by default on a
# first message from an unknown sender. So nothing is carried by the picture: the wordmark,
# the heading, the button and the fallback link are all text.
#
# **And `dir="rtl"` is repeated on every cell that holds Hebrew, rather than being set once on
# the document.** Gmail throws away `<html>` and `<body>` and drops their content into a
# container of its own, so a direction declared up there never arrives - the paragraph is then
# laid out left-to-right and the Hebrew runs inside it come out in the wrong order. The
# sentence still contains the right words, which is what makes it look like scrambled text
# rather than a missing attribute.
#
# The two runs that are genuinely left-to-right - the wordmark and the fallback URL - say so
# themselves, or the surrounding RTL context would reorder their punctuation.

SHELL = """\
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background-color:#0f1115;">
<table dir="rtl" role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:#0f1115;padding:28px 12px;direction:rtl;">
  <tr><td align="center" dir="rtl" style="direction:rtl;">

    <table dir="rtl" role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="max-width:520px;background-color:#161a21;border-radius:14px;overflow:hidden;direction:rtl;">

      <!-- the product's one line of gold, the same signature the app carries -->
      <tr><td style="height:3px;background-color:#f0b90b;line-height:3px;font-size:0;">&nbsp;</td></tr>

      <tr><td align="center" style="padding:26px 26px 0 26px;">
        <img src="cid:larson" width="88" height="88" alt=""
             style="display:block;border:0;outline:none;text-decoration:none;">
      </td></tr>

      <tr><td align="center" dir="ltr" style="padding:10px 26px 0 26px;direction:ltr;
             font-family:Arial,Helvetica,sans-serif;font-size:13px;letter-spacing:3px;
             color:#f0b90b;font-weight:bold;">LARSON</td></tr>

      <tr><td align="center" dir="rtl" style="padding:14px 26px 0 26px;direction:rtl;
             font-family:Arial,Helvetica,sans-serif;font-size:21px;line-height:1.4;
             color:#e8e8e8;font-weight:bold;">{heading}</td></tr>

      <tr><td align="center" dir="rtl" style="padding:14px 26px 0 26px;direction:rtl;
             font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.85;
             color:#a8adb8;">{body}</td></tr>

      {action}

      <tr><td style="padding:22px 26px 0 26px;">
        <div style="height:1px;background-color:#23262f;line-height:1px;font-size:0;">&nbsp;</div>
      </td></tr>

      <tr><td align="center" dir="rtl" style="padding:16px 26px 26px 26px;direction:rtl;
             font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.8;
             color:#6b7280;">{footer}</td></tr>

    </table>

    <table dir="rtl" role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="max-width:520px;direction:rtl;">
      <tr><td align="center" dir="rtl" style="padding:16px 20px 0 20px;direction:rtl;
             font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.8;
             color:#4a505c;">
        Larson — כלי אנליטי־חינוכי בלבד. אינו מהווה ייעוץ השקעות.
      </td></tr>
    </table>

  </td></tr>
</table>
</body>
</html>
"""


# A button made of a table cell rather than a styled <a>, which is the only shape Outlook
# renders as a button at all. The URL is repeated as plain text underneath it, because a
# button is unclickable in a client that shows the message as text.
ACTION = """\
      <tr><td align="center" dir="rtl" style="padding:24px 26px 0 26px;direction:rtl;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          <tr><td align="center" bgcolor="#f0b90b" style="border-radius:8px;">
            <a href="{link}" dir="rtl" style="display:inline-block;padding:13px 30px;
               font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;
               color:#0f1115;text-decoration:none;border-radius:8px;direction:rtl;">{label}</a>
          </td></tr>
        </table>
      </td></tr>

      <tr><td align="center" dir="rtl" style="padding:16px 26px 0 26px;direction:rtl;
             font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.7;
             color:#6b7280;word-break:break-all;">
        אם הכפתור לא עובד, העתק את הכתובת הזו לדפדפן:<br>
        <span dir="ltr" style="color:#8b909c;direction:ltr;unicode-bidi:embed;
              display:inline-block;">{link}</span>
      </td></tr>
"""



# ------------------------- THE THREE MESSAGES ------------------------- #

VERIFY_SUBJECT = "אישור כתובת המייל שלך ב-Larson"

VERIFY_TEXT = """שלום {name},

כדי לסיים את ההרשמה ל-Larson, אשר את כתובת המייל הזו:

{link}

הקישור תקף ל-{hours} שעות. אם לא נרשמת ל-Larson, אפשר להתעלם מההודעה הזו - לא נפתח חשבון בלי האישור.

-- Larson
"""

VERIFY_HEADING = "עוד לחיצה אחת"
VERIFY_BODY = ("שלום {name}, כדי להפעיל את החשבון שלך ב-Larson צריך לאשר "
               "שהכתובת הזו באמת שלך.")
VERIFY_FOOTER = ("הקישור תקף ל-{hours} שעות.<br>"
                 "אם לא נרשמת ל-Larson — אפשר להתעלם מההודעה. בלי האישור לא נפתח חשבון.")


RESET_SUBJECT = "איפוס הסיסמה שלך ב-Larson"

RESET_TEXT = """שלום {name},

התקבלה בקשה לאיפוס הסיסמה שלך ב-Larson. כדי לבחור סיסמה חדשה:

{link}

הקישור תקף ל-{hours} שעות וניתן לשימוש פעם אחת.

אם לא ביקשת לאפס את הסיסמה - אין צורך לעשות דבר, והסיסמה הנוכחית שלך נשארת בתוקף.

-- Larson
"""

RESET_HEADING = "בחירת סיסמה חדשה"
RESET_BODY = "שלום {name}, התקבלה בקשה לאפס את הסיסמה לחשבון שלך ב-Larson."
RESET_FOOTER = ("הקישור תקף ל-{hours} שעות וניתן לשימוש פעם אחת.<br>"
                "<b style=\"color:#8b909c;\">אם לא ביקשת את זה</b> — אין צורך לעשות דבר, "
                "והסיסמה הנוכחית שלך נשארת בתוקף.")


CHANGED_SUBJECT = "הסיסמה שלך ב-Larson הוחלפה"

CHANGED_TEXT = """שלום {name},

הסיסמה לחשבון שלך ב-Larson הוחלפה זה עתה, וכל החיבורים האחרים לחשבון נותקו.

אם זה היית אתה - אין צורך לעשות דבר.

אם לא אתה עשית את זה, מישהו אחר ככל הנראה קיבל גישה לחשבון שלך. אפס את הסיסמה מיד
דרך "שכחת סיסמה?" במסך ההתחברות, ואם אינך מצליח - פנה אלינו.

-- Larson
"""

CHANGED_HEADING = "הסיסמה שלך הוחלפה"
CHANGED_BODY = ("שלום {name}, הסיסמה לחשבון שלך ב-Larson הוחלפה זה עתה, "
                "וכל החיבורים האחרים לחשבון נותקו.")
CHANGED_FOOTER = ("אם זה היית אתה — אין צורך לעשות דבר.<br>"
                  "<b style=\"color:#e8797d;\">אם לא אתה עשית את זה</b> — אפס את הסיסמה מיד "
                  "דרך \"שכחת סיסמה?\" במסך ההתחברות.")



class _Message(EmailMultiAlternatives):
    r"""
    A message whose HTML part carries the mark inside it.

    The structure an inline image needs is:

        multipart/alternative
          |- text/plain
          \- multipart/related
               |- text/html
               \- image/png   (Content-ID: larson)

    **The picture has to sit inside the HTML branch, not beside it.** Attached at the top
    level it is a file the reader is offered rather than something the message draws, and
    clients show it as a paperclip.

    Django used to expose `mixed_subtype` for this and **removed it in 6.0**, with nothing
    put in its place - so the body is rebuilt here after Django has done the part that is
    genuinely fiddly and worth keeping: the headers, the address sanitising and the encoding.
    """

    def __init__(self, *args, inline = (), **kwargs):
        self.inline = list(inline)
        super().__init__(*args, **kwargs)

    def message(self, *args, **kwargs):
        # The arguments are passed straight through rather than being named: the SMTP backend
        # calls this with a `policy` and the in-memory one used by the tests calls it bare, so
        # a signature that only fits one of them fails **only in production**. It did.
        built = super().message(*args, **kwargs)

        # No picture, or a shape that is not what we expected: send what Django built. The
        # mail is written to read correctly with no image at all.
        if not self.inline or not built.is_multipart():
            return built

        parts = built.get_payload()
        if len(parts) != 2:
            return built

        plain, html = parts

        related = MIMEMultipart("related")
        related.attach(html)
        for image in self.inline:
            related.attach(image)

        built.set_payload([plain, related])
        return built


def _mark():
    """The mark as an inline part, or None if it cannot be read."""
    try:
        with open(MARK, "rb") as handle:
            image = MIMEImage(handle.read())
    except OSError:
        # Not fatal: every one of these messages is written so that it reads correctly with
        # no picture, which is also what most clients show on a first message from an
        # unknown sender.
        log.warning("could not read the mark from %s", MARK)
        return None

    image.add_header("Content-ID", "<larson>")
    image.add_header("Content-Disposition", "inline", filename = "larson.png")
    return image


def _escaped(name):
    """
    The name as it is safe to drop into an HTML body.

    Registration validates the username now, so nothing shaped like markup can reach here -
    **and a template that trusts its inputs is one validator away from being wrong anyway.**
    The plain-text half needs nothing; only the HTML half interpolates into markup.
    """
    return escape(name)


def _send(subject, text, html, address):
    """
    Delivery failure is logged and swallowed, deliberately.

    Every caller of this is a view that must answer the same way whether or not the address
    exists - see the note on enumeration in views.py. A dead mail server turning "forgot my
    password" into a 500 would break that, and would also tell the sender that the address
    was real.
    """
    try:
        mark = _mark()

        message = _Message(subject, text, settings.DEFAULT_FROM_EMAIL, [address],
                           inline = [mark] if mark else [])
        message.attach_alternative(html, "text/html")

        message.send(fail_silently = False)
        return True
    except Exception:
        log.exception("could not send %r to %s", subject, address)
        return False



def _html(heading, body, footer, link = None, label = None):
    action = ACTION.format(link = link, label = label) if link else ""
    return SHELL.format(heading = heading, body = body, footer = footer, action = action)



def send_verification(user):
    link = (f"{settings.FRONTEND_URL}/authentication/verify"
            f"/{pack_uid(user)}/{verification_token.make_token(user)}")

    return _send(
        VERIFY_SUBJECT,
        VERIFY_TEXT.format(name = user.username, link = link, hours = HOURS),
        _html(VERIFY_HEADING,
              VERIFY_BODY.format(name = _escaped(user.username)),
              VERIFY_FOOTER.format(hours = HOURS),
              link, "אישור הכתובת"),
        user.email)


def send_password_reset(user):
    link = (f"{settings.FRONTEND_URL}/authentication/reset"
            f"/{pack_uid(user)}/{default_token_generator.make_token(user)}")

    return _send(
        RESET_SUBJECT,
        RESET_TEXT.format(name = user.username, link = link, hours = HOURS),
        _html(RESET_HEADING,
              RESET_BODY.format(name = _escaped(user.username)),
              RESET_FOOTER.format(hours = HOURS),
              link, "בחירת סיסמה חדשה"),
        user.email)


def send_password_changed(user):
    """
    **The one mail here that is not asking for anything - it is telling.**

    A password change that nobody is told about is a password change an attacker can make in
    silence, and the real owner finds out when he can no longer get in. This is the message
    that turns a quiet takeover into something the owner sees the same minute.

    It goes out after both routes to a new password: the reset link, and the change made from
    inside the account. It carries no button, because there is nothing to confirm - and a
    button in a security notice is exactly the shape a phishing mail takes.
    """
    return _send(
        CHANGED_SUBJECT,
        CHANGED_TEXT.format(name = user.username),
        _html(CHANGED_HEADING,
              CHANGED_BODY.format(name = _escaped(user.username)),
              CHANGED_FOOTER),
        user.email)


# ------------------------- THE WEEKLY SUMMARY ------------------------- #
#
# **The only mail here that is neither asking nor warning - it is the product, arriving.**
#
# Which is the whole reason it is allowed to exist. A weekly "you have not updated" is a nudge,
# and a nudge gets unsubscribed and then reported; `digest.py` is the half of this feature that
# decides not to send one. What reaches the inbox is the week itself, and the sharpest thing in
# it **with the trade that proves it, by date and by time** - the same line the chat shows.
#
# **Every one of these carries an unsubscribe link, and it works without logging in.** Asking
# somebody to sign in to stop receiving email is how a sender earns a spam complaint, and a
# complaint lands on the domain that also carries the verification mail.

DIGEST_SUBJECT = "השבוע שלך, בשורה אחת"

DIGEST_TEXT = """{name}, זה מה שלארסון ראה השבוע:

{count_text} · רווח נקי {net_pnl} · {win_rate} הצלחה
{leak_text}
הפירוט המלא בעמוד המנטור: {link}

--
לא רוצה את הסיכום הזה? {unsubscribe}
"""

DIGEST_HEADING = "השבוע שלך"

DIGEST_BODY = """\
<p style="margin:0 0 18px;">{name}, זה מה שלארסון ראה השבוע.</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="margin:0 0 20px;">
  <tr>
    <td style="padding:14px 16px; background:#13161c; border:1px solid #23262f;
               border-radius:10px;">
      <div style="font-size:15px; color:#e8e8e8; font-weight:700;">{count_text}</div>
      <div style="font-size:14px; color:#8b909c; margin-top:6px;">
        רווח נקי {net_pnl} · {win_rate} הצלחה
      </div>
    </td>
  </tr>
</table>
{leak_html}"""

DIGEST_LEAK = """\
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="margin:0 0 20px;">
  <tr>
    <td style="padding:14px 16px; background:#171a21; border:1px solid #3b3320;
               border-right:3px solid #f0b90b; border-radius:10px;">
      <div style="font-size:14px; color:#f0b90b; font-weight:700;">{title}</div>
      <div style="font-size:14px; color:#c9ccd3; margin-top:8px;">{detail}</div>
      {example}
    </td>
  </tr>
</table>"""

DIGEST_EXAMPLE = """\
<div style="font-size:13px; color:#8b909c; margin-top:10px; direction:ltr; text-align:right;
            font-family:ui-monospace, Menlo, monospace;">{line}</div>"""

DIGEST_FOOTER = ('הסיכום הזה נשלח פעם בשבוע, <b>ורק כשיש מה לסכם</b>.<br>'
                 '<a href="{unsubscribe}" style="color:#8b909c;">לא רוצה לקבל אותו</a>')


NUDGE_SUBJECT = "לארסון לא ראה ממך עסקה {days} ימים"

NUDGE_TEXT = """{name}, עברו {days} ימים מאז שלארסון ראה ממך עסקה.

אם סחרת ולא עדכנת — הוא לא יכול להשוות מה שלא קיבל.
לעדכן אותו: {link}

--
זו תזכורת אחת, לא שבועית. {unsubscribe}
"""

NUDGE_HEADING = "עברו {days} ימים"

NUDGE_BODY = """\
<p style="margin:0 0 18px;">{name}, עברו <b>{days} ימים</b> מאז שלארסון ראה ממך עסקה.</p>
<p style="margin:0 0 18px; color:#8b909c;">אם סחרת ולא עדכנת — הוא לא יכול להשוות מה שלא
קיבל, והתחקיר הבא יהיה על תקופה ולא על סשן.</p>"""

# **One reminder per silence, and the mail says so.** A trader who knows it will not repeat
# has no reason to reach for the spam button, which is the entire point.
NUDGE_FOOTER = ('זו תזכורת אחת על הפער הזה — <b>לא אחת לשבוע</b>.<br>'
                '<a href="{unsubscribe}" style="color:#8b909c;">לבטל את הסיכום השבועי</a>')



def send_weekly_digest(user, payload, unsubscribe):
    """The week, with the sharpest finding and the trade that proves it."""
    link = f"{settings.FRONTEND_URL}/mentor"

    leak_text = ""
    leak_html = ""

    if payload.get("leak_title"):
        example_html = ""
        example_text = ""

        if payload.get("leak_example"):
            example_html = DIGEST_EXAMPLE.format(line = _escaped(payload["leak_example"]))
            example_text = f"\n   {payload['leak_example']}"

        leak_html = DIGEST_LEAK.format(
            title = _escaped(payload["leak_title"]),
            detail = _escaped(payload["leak_detail"]),
            example = example_html)

        leak_text = (f"\n{payload['leak_title']}\n"
                     f"   {payload['leak_detail']}{example_text}\n")

    return _send(
        DIGEST_SUBJECT,
        DIGEST_TEXT.format(name = user.username, link = link, unsubscribe = unsubscribe,
                           leak_text = leak_text, **_plain(payload)),
        _html(DIGEST_HEADING,
              DIGEST_BODY.format(name = _escaped(user.username), leak_html = leak_html,
                                 **_escaped_payload(payload)),
              DIGEST_FOOTER.format(unsubscribe = unsubscribe)),
        user.email)


def send_weekly_nudge(user, days, unsubscribe):
    """One reminder, once per silence."""
    link = f"{settings.FRONTEND_URL}/mentor"

    return _send(
        NUDGE_SUBJECT.format(days = days),
        NUDGE_TEXT.format(name = user.username, days = days, link = link,
                          unsubscribe = unsubscribe),
        _html(NUDGE_HEADING.format(days = days),
              NUDGE_BODY.format(name = _escaped(user.username), days = days),
              NUDGE_FOOTER.format(unsubscribe = unsubscribe)),
        user.email)


def _plain(payload):
    """The figures as they are, for the text part."""
    return {key: payload.get(key, "") for key in ("count_text", "net_pnl", "win_rate")}


def _escaped_payload(payload):
    """**The template escapes its own inputs rather than trusting them.**

    Every figure here was formatted by `analytics/formatting.py` and is safe - but a template
    that trusts its input is one validator away from being wrong, which is the same reasoning
    that put `_escaped` on the username.
    """
    return {key: _escaped(payload.get(key, "")) for key in ("count_text", "net_pnl", "win_rate")}
