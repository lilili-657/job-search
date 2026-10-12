"""Retrieve page content without interpreting it or executing JavaScript."""

from dataclasses import dataclass
import math

import requests
from urllib3.exceptions import ReadTimeoutError


@dataclass(frozen=True)
class JobPageFetchResult:
    raw_html: str
    status_code: int
    final_url: str


class JobPageFetchError(Exception):
    """No complete response could be retrieved."""


class JobPageFetchTimeout(JobPageFetchError):
    """The connection or response read timed out."""


class JobPageFetcher:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive.")
        self.timeout_seconds = timeout_seconds

    def fetch(self, job_url: str) -> JobPageFetchResult:
        """Follow redirects and retain all HTTP statuses, including errors.

        raw_html is the decoded, otherwise unprocessed response body; the
        server may return an error page or non-HTML content. The timeout is
        a connect/read inactivity timeout, not a total elapsed-time deadline.
        """
        try:
            with requests.get(
                job_url, timeout=self.timeout_seconds, allow_redirects=True,
                stream=True,
            ) as response:
                return JobPageFetchResult(
                    raw_html=response.text,
                    status_code=response.status_code,
                    final_url=response.url,
                )
        except requests.exceptions.Timeout as exc:
            raise JobPageFetchTimeout("Job page request timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            # Requests wraps body-read timeouts in ConnectionError.
            if exc.args and isinstance(exc.args[0], ReadTimeoutError):
                raise JobPageFetchTimeout("Job page response timed out.") from exc
            raise JobPageFetchError("Unable to retrieve job page.") from exc
        except requests.exceptions.RequestException as exc:
            raise JobPageFetchError("Unable to retrieve job page.") from exc
