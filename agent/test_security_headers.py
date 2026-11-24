"""Every response carries baseline security headers (hermetic TestClient)."""
import unittest

from starlette.testclient import TestClient

import web_server

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "strict-transport-security": "max-age=31536000; includeSubDomains",
}
CSP_REQUIRED = [
    "default-src 'self'", "script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline'",
    "font-src 'self'", "img-src 'self' data:", "connect-src 'self'", "object-src 'none'",
    "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
]


class SecurityHeadersTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web_server.app)

    def _check(self, path):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200, path)
        for k, v in EXPECTED.items():
            self.assertEqual(r.headers.get(k), v, f"{path} {k}")
        directives = [d.strip() for d in r.headers["content-security-policy"].split(";")]
        for d in CSP_REQUIRED:
            self.assertIn(d, directives, f"{path} CSP")
        self.assertNotIn("unsafe-eval", r.headers["content-security-policy"])
        self.assertNotIn("google", r.headers["content-security-policy"])

    def test_healthz(self):
        self._check("/healthz")

    def test_public_html_page(self):
        self._check("/")

    def test_static_html_page(self):
        self._check("/standing-interview.html")


if __name__ == "__main__":
    unittest.main()
