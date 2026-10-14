from rest_framework.test import APIClient

from apps.common.testing import TenantTestCase


class AuthenticationTests(TenantTestCase):
    def test_csrf_bootstrap_is_empty_204_and_sets_cookie(self):
        response = APIClient().get("/api/auth/csrf/", HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertIn("csrftoken", response.cookies)
        self.assertEqual(response.cookies["csrftoken"]["httponly"], "")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertEqual(response["Access-Control-Allow-Credentials"], "true")

    def test_login_authenticates_and_failed_login_is_generic(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.get("/api/auth/csrf/")
        csrf_token = self.client.cookies["csrftoken"].value
        response = self.client.post(
            "/api/auth/login/",
            {"username": "dispatch", "password": "dispatch-password"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "dispatcher")
        self.assertEqual(response.json()["user"]["organization_name"], "Org A")
        self.assertIn("csrftoken", response.cookies)
        failed = self.client.post(
            "/api/auth/login/",
            {"username": "dispatch", "password": "incorrect"},
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(failed.status_code, 400)
        self.assertEqual(failed.json()["error"]["details"]["detail"], "Invalid credentials.")
        self.assertEqual(self.client.get("/api/me/").status_code, 200)
        logged_out = self.client.post(
            "/api/logout/", {}, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value
        )
        self.assertEqual(logged_out.status_code, 204)
