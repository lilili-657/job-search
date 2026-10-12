import os
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

import requests
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.transcribe import transcribe


class TranscribeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.env = patch.dict(os.environ, {"OPENAI_API_KEY": "test-server-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.patch = patch("backend.app.api.transcribe.requests.post")
        self.post = self.patch.start()
        self.addCleanup(self.patch.stop)
        self.response = MagicMock()
        self.response.status_code = 200
        self.response.ok = True
        self.response.json.return_value = {"text": "Spoken notes."}
        self.post.return_value.__enter__.return_value = self.response

    def upload(self, data=b"audio bytes", filename="recording.webm"):
        return self.client.post("/api/transcribe", files={
            "audio": (filename, data, "audio/webm;codecs=opus")
        })

    def test_returns_only_text_and_sends_audio_with_server_key(self):
        def capture(url, **kwargs):
            self.assertEqual(url, "https://api.openai.com/v1/audio/transcriptions")
            self.assertEqual(kwargs["headers"], {"Authorization": "Bearer test-server-key"})
            self.assertEqual(kwargs["data"], {"model": "gpt-transcribe", "response_format": "json"})
            filename, stream, mime = kwargs["files"]["file"]
            self.assertEqual(filename, "recording.webm")
            self.assertEqual(stream.read(), b"audio bytes")
            self.assertEqual(mime, "audio/webm;codecs=opus")
            self.stream = stream
            return self.post.return_value
        self.post.side_effect = capture
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"text": "Spoken notes."})
        self.assertTrue(self.stream.closed)

    def test_missing_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertEqual(self.upload().status_code, 503)
        self.post.assert_not_called()

    def test_invalid_empty_missing_and_oversize_uploads(self):
        self.assertEqual(self.upload(b"").status_code, 422)
        self.assertEqual(self.upload(filename="notes.txt").status_code, 422)
        self.assertEqual(self.client.post("/api/transcribe").status_code, 422)
        with patch("backend.app.api.transcribe.MAX_AUDIO_BYTES", 3):
            self.assertEqual(self.upload(b"1234").status_code, 413)
        self.post.assert_not_called()

    def test_provider_errors_are_sanitized(self):
        for upstream, expected in ((400, 422), (401, 503), (403, 503), (429, 429), (500, 502)):
            with self.subTest(upstream=upstream):
                self.response.status_code = upstream
                self.response.ok = False
                self.response.text = "secret provider details"
                response = self.upload()
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("secret", response.text)
                self.assertNotIn("test-server-key", response.text)
                if upstream in (401, 403):
                    self.assertIn(f"({upstream})", response.json()["detail"])

    def test_network_errors_and_cleanup(self):
        for error, expected in ((requests.Timeout(), 504), (requests.ConnectionError(), 502)):
            with self.subTest(error=error):
                self.post.side_effect = error
                stream = BytesIO(b"audio")
                with self.assertRaises(HTTPException) as caught:
                    transcribe(UploadFile(file=stream, filename="recording.webm"))
                self.assertEqual(caught.exception.status_code, expected)
                self.assertTrue(stream.closed)

    def test_429_distinguishes_quota_from_temporary_limits(self):
        self.response.status_code = 429
        for error, expected in (
            ({"code": "credit_balance_exhausted"}, "credits are exhausted"),
            ({"code": "project_spend_limit_exceeded", "type": "insufficient_quota"}, "project spend limit"),
            ({"code": "organization_spend_limit_exceeded"}, "organization spend limit"),
            ({"code": "organization_usage_limit_exceeded"}, "organization usage limit"),
            ({"code": "insufficient_quota"}, "quota is unavailable"),
            ({"type": "insufficient_quota"}, "quota is unavailable"),
            ({"type": "rate_limit_error"}, "temporarily rate limited"),
            ({"code": "slow_down"}, "too quickly"),
            ({"code": "unknown", "message": "secret"}, "did not identify"),
            ({"code": []}, "did not identify"),
        ):
            with self.subTest(error=error):
                self.response.json.return_value = {"error": error}
                response = self.upload()
                self.assertEqual(response.status_code, 429)
                self.assertIn(expected, response.json()["detail"])
                self.assertNotIn("secret", response.text)
        self.response.json.side_effect = ValueError("not JSON")
        self.assertEqual(self.upload().status_code, 429)

    def test_invalid_and_empty_provider_response(self):
        for value, status in (({}, 502), ({"text": 12}, 502), ({"text": "  "}, 422)):
            with self.subTest(value=value):
                self.response.json.return_value = value
                self.assertEqual(self.upload().status_code, status)
        self.response.json.side_effect = ValueError("not JSON")
        self.assertEqual(self.upload().status_code, 502)

    def test_analyze_is_not_called_or_changed(self):
        response = self.client.post("/api/analyze", data={
            "job_url": "https://example.com/job", "additional_notes": "Typed notes",
        }, files={"resumes": ("resume.pdf", b"metadata only", "application/pdf")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["notes_length"], 11)
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
