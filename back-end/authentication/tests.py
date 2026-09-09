from rest_framework.test import APITestCase
from rest_framework import status

from django.contrib.auth.models import User



# ------------------------- AUTHENTICATION TESTS START ------------------------- #

class AuthenticationTests(APITestCase):

    def setUp(self):
        self.user_data = {"username": "omer", "password": "Aa123456", "email": "omer@larson.com"}


    # ------------- REGISTRATION:
    def test_register_creates_user(self):
        response = self.client.post("/authentication/register/", self.user_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="omer").exists())


    def test_register_rejects_duplicate_username(self):
        self.client.post("/authentication/register/", self.user_data)
        response = self.client.post("/authentication/register/", self.user_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(username="omer").count(), 1)


    # ------------- LOGIN:
    def test_login_returns_tokens_with_username_claim(self):
        self.client.post("/authentication/register/", self.user_data)
        response = self.client.post("/authentication/login/", {"username": "omer", "password": "Aa123456"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


    def test_index_requires_authentication(self):
        response = self.client.get("/authentication/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_index_returns_username_when_logged_in(self):
        self.client.post("/authentication/register/", self.user_data)
        tokens = self.client.post("/authentication/login/", {"username": "omer", "password": "Aa123456"}).data

        self.client.credentials(HTTP_AUTHORIZATION = f"Bearer {tokens['access']}")
        response = self.client.get("/authentication/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "omer")


    # ------------- LOGOUT:
    def test_logout_blacklists_refresh_token(self):
        self.client.post("/authentication/register/", self.user_data)
        tokens = self.client.post("/authentication/login/", {"username": "omer", "password": "Aa123456"}).data

        self.client.credentials(HTTP_AUTHORIZATION = f"Bearer {tokens['access']}")
        response = self.client.post("/authentication/logout/", {"refresh_token": tokens["refresh"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

# ------------------------- AUTHENTICATION TESTS END ------------------------- #
