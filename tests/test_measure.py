"""HTTP time-to-first-byte measurement."""

from __future__ import annotations

import socket
import ssl
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest

from lupaxa.time_to_first_byte.measure import TimingResult, measure, run_measurements, summarize

REDIRECT_HEADER_PAUSE = 0.1
FAILURE_DECISION_PAUSE = 0.3
FAKE_ADDRESS = (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 9))


class _FakeSocket:
    def __init__(self, connect_error: BaseException | None = None) -> None:
        self._connect_error = connect_error

    def settimeout(self, timeout: float) -> None:
        pass

    def connect(self, sockaddr: tuple[str, int]) -> None:
        if self._connect_error is not None:
            raise self._connect_error

    def close(self) -> None:
        pass


class _Handler(BaseHTTPRequestHandler):
    recorded_headers: dict[str, str] = {}
    body_gate = threading.Event()

    def do_GET(self) -> None:
        type(self).recorded_headers = dict(self.headers)
        if self.path == "/missing":
            self.send_error(404)
            return
        if self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
            return
        if self.path == "/bad-port":
            self.send_response(302)
            self.send_header("Location", "//127.0.0.1:70000/")
            self.end_headers()
            return
        if self.path == "/bad-scheme":
            self.send_response(302)
            self.send_header("Location", "ftp://127.0.0.1/nope")
            self.end_headers()
            return
        if self.path == "/body-location":
            self.wfile.write(b"HTTP/1.1 302 Found\r\n\r\nLocation: /final\r\n")
            return
        if self.path == "/bounce":
            self.send_response(302)
            self.end_headers()
            return
        if self.path == "/loop":
            self.send_response(302)
            self.send_header("Location", "/loop")
            self.end_headers()
            return
        if self.path == "/slow-bounce":
            self.wfile.write(b"HTTP/1.1 302 Found\r\n")
            self.wfile.flush()
            time.sleep(REDIRECT_HEADER_PAUSE)
            self.wfile.write(b"\r\n")
            return
        if self.path == "/slow-loop":
            self.wfile.write(b"HTTP/1.1 302 Found\r\n")
            self.wfile.flush()
            time.sleep(REDIRECT_HEADER_PAUSE)
            self.wfile.write(b"Location: /slow-loop\r\n\r\n")
            return
        if self.path == "/incomplete-status":
            self.wfile.write(b"H")
            self.wfile.flush()
            time.sleep(FAILURE_DECISION_PAUSE)
            return
        if self.path == "/malformed-status":
            self.wfile.write(b"H")
            self.wfile.flush()
            time.sleep(FAILURE_DECISION_PAUSE)
            self.wfile.write(b"TTP/1.1 not-a-status\r\n")
            return
        if self.path == "/incomplete-redirect-headers":
            self.wfile.write(b"HTTP/1.1 302 \r\n")
            self.wfile.flush()
            time.sleep(FAILURE_DECISION_PAUSE)
            return
        self.send_response(200)
        self.end_headers()
        if self.path == "/blocked":
            self.wfile.flush()
            type(self).body_gate.wait(timeout=2)
        self.wfile.write(b"body")

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server_url() -> Iterator[str]:
    _Handler.recorded_headers = {}
    _Handler.body_gate.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        _Handler.body_gate.set()
        server.shutdown()
        thread.join()
        server.server_close()


def _sample(ok: bool, ttfb: float, sequence: int = 0) -> TimingResult:
    return TimingResult(
        ok=ok,
        url="http://example.com/",
        sequence=sequence,
        dns_ms=1.0,
        connect_ms=2.0,
        tls_ms=0.0,
        ttfb_ms=ttfb,
        status=200 if ok else None,
        redirects=0,
        final_url="http://example.com/",
        detail="ok" if ok else "connection refused",
    )


def test_summarize_empty() -> None:
    summary = summarize([])
    assert summary.total == 0
    assert summary.passed == 0
    assert summary.failed == 0
    assert summary.fail_percent == 0.0
    assert summary.ttfb_min_ms is None
    assert summary.ttfb_avg_ms is None
    assert summary.ttfb_max_ms is None
    assert summary.results == ()


def test_summarize_ignores_failures_for_ttfb_stats() -> None:
    summary = summarize([_sample(True, 10.0, 0), _sample(False, 99.0, 1), _sample(True, 30.0, 2)])
    assert summary.total == 3
    assert summary.passed == 2
    assert summary.failed == 1
    assert summary.fail_percent == pytest.approx(100 / 3)
    assert summary.ttfb_min_ms == 10.0
    assert summary.ttfb_avg_ms == 20.0
    assert summary.ttfb_max_ms == 30.0


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("   ", "url must not be empty"),
        ("ftp://example.com/", "url scheme must be http or https"),
        ("http:///no-host", "url must include a host"),
    ],
)
def test_measure_rejects_invalid_urls(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        measure(url)


@pytest.mark.parametrize("url", ["http://example.com:not-a-port/", "http://example.com:70000/"])
def test_measure_rejects_invalid_input_ports(url: str) -> None:
    with pytest.raises(ValueError, match="Port "):
        measure(url)


def test_measure_rejects_invalid_options() -> None:
    with pytest.raises(ValueError, match="timeout must be greater than 0"):
        measure("http://example.com/", timeout=0)
    with pytest.raises(ValueError, match="max_redirects must be 0 or greater"):
        measure("http://example.com/", max_redirects=-1)


def test_measure_gets_first_byte_and_sends_headers(server_url: str) -> None:
    result = measure(f"{server_url}/", sequence=7)

    assert result.ok
    assert result.status == 200
    assert result.redirects == 0
    assert result.tls_ms == 0.0
    assert result.ttfb_ms >= 0
    assert result.detail == "ok"
    assert result.final_url == f"{server_url}/"
    assert result.sequence == 7
    assert _Handler.recorded_headers["Cache-Control"] == "no-cache"
    assert _Handler.recorded_headers["Connection"] == "close"
    assert _Handler.recorded_headers["User-Agent"].startswith("lupaxa-time-to-first-byte/")
    assert "Expect" not in _Handler.recorded_headers


def test_measure_returns_before_response_body(server_url: str) -> None:
    result = measure(f"{server_url}/blocked", timeout=2)

    assert result.ok
    assert not _Handler.body_gate.is_set()


def test_measure_accepts_http_error_status(server_url: str) -> None:
    result = measure(f"{server_url}/missing")

    assert result.ok
    assert result.status == 404


def test_measure_follows_redirect(server_url: str) -> None:
    result = measure(f"{server_url}/redir")

    assert result.ok
    assert result.status == 200
    assert result.redirects == 1
    assert result.final_url.endswith("/final")


def test_measure_returns_failure_for_redirect_with_invalid_port(server_url: str) -> None:
    result = measure(f"{server_url}/bad-port")

    assert not result.ok
    assert result.detail == "OS error: invalid port in URL"


def test_measure_returns_failure_for_redirect_with_non_http_scheme(server_url: str) -> None:
    result = measure(f"{server_url}/bad-scheme")

    assert not result.ok
    assert result.detail == "OS error: redirect scheme must be http or https"


def test_measure_ignores_location_in_response_body(server_url: str) -> None:
    result = measure(f"{server_url}/body-location")

    assert not result.ok
    assert result.detail == "redirect missing location"


def test_measure_rejects_redirect_without_location(server_url: str) -> None:
    result = measure(f"{server_url}/bounce")

    assert not result.ok
    assert result.detail == "redirect missing location"
    assert result.status is None


def test_redirect_without_location_ttfb_includes_complete_headers(server_url: str) -> None:
    result = measure(f"{server_url}/slow-bounce")

    assert not result.ok
    assert result.detail == "redirect missing location"
    assert result.ttfb_ms > REDIRECT_HEADER_PAUSE * 1000


def test_measure_enforces_redirect_limit(server_url: str) -> None:
    result = measure(f"{server_url}/loop", max_redirects=0)

    assert not result.ok
    assert result.detail == "too many redirects"
    assert result.redirects == 0


def test_redirect_limit_ttfb_includes_complete_headers(server_url: str) -> None:
    result = measure(f"{server_url}/slow-loop", max_redirects=0)

    assert not result.ok
    assert result.detail == "too many redirects"
    assert result.ttfb_ms > REDIRECT_HEADER_PAUSE * 1000


def test_incomplete_status_ttfb_includes_failure_delay(server_url: str) -> None:
    result = measure(f"{server_url}/incomplete-status")

    assert not result.ok
    assert result.ttfb_ms > 250


def test_malformed_status_ttfb_includes_failure_delay(server_url: str) -> None:
    result = measure(f"{server_url}/malformed-status")

    assert not result.ok
    assert result.ttfb_ms > 250


def test_incomplete_redirect_headers_ttfb_includes_failure_delay(server_url: str) -> None:
    result = measure(f"{server_url}/incomplete-redirect-headers")

    assert not result.ok
    assert result.ttfb_ms > 250


def test_measure_strips_url_whitespace(server_url: str) -> None:
    result = measure(f"  {server_url}/  ")

    assert result.ok
    assert result.url == f"{server_url}/"


def test_measure_dns_failure() -> None:
    with patch(
        "lupaxa.time_to_first_byte.measure.socket.getaddrinfo",
        side_effect=socket.gaierror("name resolution failed"),
    ):
        result = measure("http://example.com/")

    assert not result.ok
    assert result.detail == "name resolution failed"
    assert result.connect_ms == 0
    assert result.tls_ms == 0
    assert result.status is None


def test_measure_connect_timeout() -> None:
    fake_socket = _FakeSocket(connect_error=TimeoutError("timed out"))
    with (
        patch(
            "lupaxa.time_to_first_byte.measure.socket.getaddrinfo",
            return_value=[FAKE_ADDRESS],
        ),
        patch(
            "lupaxa.time_to_first_byte.measure.socket.socket",
            return_value=fake_socket,
        ),
    ):
        result = measure("http://example.com/")

    assert not result.ok
    assert result.detail == "connection timed out"
    assert result.dns_ms >= 0


def test_measure_connection_refused() -> None:
    fake_socket = _FakeSocket(connect_error=ConnectionRefusedError())
    with (
        patch(
            "lupaxa.time_to_first_byte.measure.socket.getaddrinfo",
            return_value=[FAKE_ADDRESS],
        ),
        patch(
            "lupaxa.time_to_first_byte.measure.socket.socket",
            return_value=fake_socket,
        ),
    ):
        result = measure("http://example.com/")

    assert not result.ok
    assert result.detail == "connection refused"


def test_measure_os_error() -> None:
    fake_socket = _FakeSocket(connect_error=OSError("network is unreachable"))
    with (
        patch(
            "lupaxa.time_to_first_byte.measure.socket.getaddrinfo",
            return_value=[FAKE_ADDRESS],
        ),
        patch(
            "lupaxa.time_to_first_byte.measure.socket.socket",
            return_value=fake_socket,
        ),
    ):
        result = measure("http://example.com/")

    assert not result.ok
    assert result.detail.startswith("OS error:")
    assert "unreachable" in result.detail


def test_measure_tls_error() -> None:
    fake_socket = _FakeSocket()
    real_create_default_context = ssl.create_default_context

    def create_context() -> ssl.SSLContext:
        context = real_create_default_context()

        def wrap_socket(sock: socket.socket, **kwargs: object) -> socket.socket:
            raise ssl.SSLError("bad cert")

        context.wrap_socket = wrap_socket  # type: ignore[method-assign]
        return context

    with (
        patch(
            "lupaxa.time_to_first_byte.measure.socket.getaddrinfo",
            return_value=[FAKE_ADDRESS],
        ),
        patch(
            "lupaxa.time_to_first_byte.measure.socket.socket",
            return_value=fake_socket,
        ),
        patch(
            "lupaxa.time_to_first_byte.measure.ssl.create_default_context",
            create_context,
        ),
    ):
        result = measure("https://example.com/")

    assert not result.ok
    assert result.detail == "tls error"
    assert result.dns_ms >= 0
    assert result.connect_ms >= 0
    assert result.tls_ms == 0


def test_measure_https_uses_verified_context(server_url: str) -> None:
    contexts: list[ssl.SSLContext] = []
    real_create_default_context = ssl.create_default_context

    def create_context() -> ssl.SSLContext:
        context = real_create_default_context()
        contexts.append(context)
        context.wrap_socket = lambda sock, **kwargs: sock  # type: ignore[method-assign]
        return context

    with patch("lupaxa.time_to_first_byte.measure.ssl.create_default_context", create_context):
        result = measure(server_url.replace("http://", "https://", 1))

    assert contexts[0].check_hostname
    assert contexts[0].verify_mode == ssl.CERT_REQUIRED
    assert contexts[0].minimum_version == ssl.TLSVersion.TLSv1_2
    assert result.ok
    assert result.tls_ms >= 0


def test_run_measurements_repeats_for_count(server_url: str) -> None:
    summary = run_measurements(f"{server_url}/", delay=0, count=3)

    assert summary.total == 3
    assert [item.sequence for item in summary.results] == [0, 1, 2]
    assert summary.passed == 3
    assert summary.ttfb_min_ms is not None
    assert summary.ttfb_avg_ms is not None
    assert summary.ttfb_max_ms is not None
    assert summary.ttfb_min_ms <= summary.ttfb_avg_ms <= summary.ttfb_max_ms


def test_run_measurements_stops_before_first_when_asked(server_url: str) -> None:
    summary = run_measurements(
        f"{server_url}/",
        delay=0,
        count=None,
        should_stop=lambda: True,
    )

    assert summary.total == 0
    assert summary.ttfb_min_ms is None


def test_run_measurements_calls_on_result_once_per_sample(server_url: str) -> None:
    seen: list[TimingResult] = []

    summary = run_measurements(f"{server_url}/", delay=0, count=3, on_result=seen.append)

    assert len(seen) == 3
    assert seen == list(summary.results)


def test_run_measurements_sleeps_between_samples_only(server_url: str) -> None:
    with patch("lupaxa.time_to_first_byte.measure.time.sleep") as sleep:
        summary = run_measurements(f"{server_url}/", delay=0.25, count=2)

    sleep.assert_called_once_with(0.25)
    assert summary.total == 2


def test_run_measurements_rejects_invalid_delay_and_count() -> None:
    with pytest.raises(ValueError, match="delay"):
        run_measurements("http://example.com/", delay=-1, count=1, should_stop=lambda: True)
    with pytest.raises(ValueError, match="count"):
        run_measurements("http://example.com/", count=0, should_stop=lambda: True)


def test_run_measurements_all_failures_have_no_ttfb_stats() -> None:
    with patch(
        "lupaxa.time_to_first_byte.measure.measure",
        return_value=_sample(False, 99.0),
    ):
        summary = run_measurements("http://example.com/", delay=0, count=2)

    assert summary.failed == 2
    assert summary.ttfb_min_ms is None
