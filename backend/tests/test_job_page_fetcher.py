"""Exercise the real HTTP client against an isolated local server."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import time
import unittest

from backend.app.services.job_page_fetcher import (
    JobPageFetchError,
    JobPageFetcher,
    JobPageFetchTimeout,
)


HTML = "<!doctype html><html><body>Unprocessed café</body></html>"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/redirect", "/loop"):
            self.send_response(302)
            self.send_header(
                "Location", "/page" if self.path == "/redirect" else "/loop"
            )
            self.end_headers()
            return
        if self.path == "/slow":
            time.sleep(0.2)
        status = int(self.path[1:]) if self.path[1:].isdigit() else 200
        body = HTML if status == 200 else "<html>Error page</html>"
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if self.path == "/slow-body":
            self.wfile.flush()
            time.sleep(0.2)
        try:
            self.wfile.write(body.encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            pass  # The timeout test deliberately disconnects.

    def log_message(self, format, *args):
        pass


class JobPageFetcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_returns_unprocessed_html_status_and_url(self):
        result = JobPageFetcher().fetch(self.base_url + "/page")
        self.assertEqual(result.raw_html, HTML)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.final_url, self.base_url + "/page")

    def test_follows_redirect(self):
        result = JobPageFetcher().fetch(self.base_url + "/redirect")
        self.assertEqual(result.final_url, self.base_url + "/page")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.raw_html, HTML)

    def test_retains_non_200_response(self):
        for status in (403, 404, 500):
            with self.subTest(status=status):
                url = f"{self.base_url}/{status}"
                result = JobPageFetcher().fetch(url)
                self.assertEqual(result.status_code, status)
                self.assertEqual(result.raw_html, "<html>Error page</html>")
                self.assertEqual(result.final_url, url)

    def test_timeout(self):
        with self.assertRaises(JobPageFetchTimeout):
            JobPageFetcher(timeout_seconds=0.03).fetch(self.base_url + "/slow")

    def test_redirect_loop(self):
        with self.assertRaises(JobPageFetchError):
            JobPageFetcher().fetch(self.base_url + "/loop")

    def test_timeout_during_body_download(self):
        with self.assertRaises(JobPageFetchTimeout):
            JobPageFetcher(timeout_seconds=0.03).fetch(self.base_url + "/slow-body")

    def test_connection_failure(self):
        # Reserve a port without listening, so the connection is refused.
        import socket

        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            url = f"http://127.0.0.1:{reserved.getsockname()[1]}/page"
            with self.assertRaises(JobPageFetchError):
                JobPageFetcher().fetch(url)

    def test_invalid_url(self):
        with self.assertRaises(JobPageFetchError):
            JobPageFetcher().fetch("not-a-url")

    def test_invalid_timeout(self):
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                JobPageFetcher(timeout_seconds=timeout)


if __name__ == "__main__":
    unittest.main()
