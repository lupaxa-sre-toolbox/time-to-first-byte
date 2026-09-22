"""HTTP time-to-first-byte measurement."""

from __future__ import annotations

import math
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from timeit import default_timer as timer
from urllib.parse import urljoin, urlsplit

from lupaxa.time_to_first_byte.version import get_version

DEFAULT_DELAY = 1.0
DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_REDIRECTS = 10

DETAIL_OK = "ok"
DETAIL_DNS = "name resolution failed"
DETAIL_TIMEOUT = "connection timed out"
DETAIL_REFUSED = "connection refused"
DETAIL_TLS = "tls error"
DETAIL_TOO_MANY = "too many redirects"
DETAIL_NO_LOCATION = "redirect missing location"
DETAIL_OS_ERROR_PREFIX = "OS error: "
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class TimingResult:
    """Outcome of one HTTP time-to-first-byte sample."""

    ok: bool
    url: str
    sequence: int
    dns_ms: float
    connect_ms: float
    tls_ms: float
    ttfb_ms: float
    status: int | None
    redirects: int
    final_url: str
    detail: str


@dataclass(frozen=True)
class TimingSummary:
    """Aggregate of one or more samples."""

    total: int
    passed: int
    failed: int
    fail_percent: float
    ttfb_min_ms: float | None
    ttfb_avg_ms: float | None
    ttfb_max_ms: float | None
    results: tuple[TimingResult, ...]


def _ms(started: float) -> float:
    return 1000 * (timer() - started)


def _require_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise ValueError("url must not be empty")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise ValueError("url scheme must be http or https")
    if not parts.hostname:
        raise ValueError("url must include a host")
    _ = parts.port
    return url


def _require_timeout(timeout: float) -> float:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be greater than 0")
    return timeout


def _require_max_redirects(max_redirects: int) -> int:
    if max_redirects < 0:
        raise ValueError("max_redirects must be 0 or greater")
    return max_redirects


def _require_delay(delay: float) -> float:
    if not math.isfinite(delay) or delay < 0:
        raise ValueError("delay must be 0 or greater")
    return delay


def _require_count(count: int | None) -> int | None:
    if count is None:
        return None
    if count < 1:
        raise ValueError("count must be greater than 0")
    return count


def _result(
    *,
    ok: bool,
    url: str,
    sequence: int,
    dns_ms: float,
    connect_ms: float,
    tls_ms: float,
    ttfb_ms: float | None,
    status: int | None,
    redirects: int,
    final_url: str,
    detail: str,
    sample_started: float,
) -> TimingResult:
    return TimingResult(
        ok=ok,
        url=url,
        sequence=sequence,
        dns_ms=dns_ms,
        connect_ms=connect_ms,
        tls_ms=tls_ms,
        ttfb_ms=_ms(sample_started) if ttfb_ms is None else ttfb_ms,
        status=status if ok else None,
        redirects=redirects,
        final_url=final_url,
        detail=detail,
    )


def measure(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    sequence: int = 0,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> TimingResult:
    """Measure the time until the first response byte for one URL."""
    requested_url = _require_url(url)
    timeout = _require_timeout(timeout)
    max_redirects = _require_max_redirects(max_redirects)
    sample_started = timer()
    current_url = requested_url
    redirects = 0

    def build_result(
        ok: bool,
        detail: str,
        dns_ms: float,
        connect_ms: float,
        tls_ms: float,
        ttfb_ms: float | None,
        status: int | None,
        redirects: int,
        final_url: str,
    ) -> TimingResult:
        return _result(
            ok=ok,
            url=requested_url,
            sequence=sequence,
            dns_ms=dns_ms,
            connect_ms=connect_ms,
            tls_ms=tls_ms,
            ttfb_ms=ttfb_ms,
            status=status,
            redirects=redirects,
            final_url=final_url,
            detail=detail,
            sample_started=sample_started,
        )

    while True:
        dns_ms = connect_ms = tls_ms = 0.0
        ttfb_ms: float | None = None
        status: int | None = None
        connection: socket.socket | None = None
        detail: str | None = None
        parts = urlsplit(current_url)
        hostname = parts.hostname
        default_port = 443 if parts.scheme == "https" else 80
        port = parts.port or default_port

        try:
            if hostname is None:
                raise OSError("redirect URL has no host")
            phase_started = timer()
            try:
                addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            finally:
                dns_ms = _ms(phase_started)
            family, socktype, proto, _, sockaddr = addresses[0]

            connection = socket.socket(family, socktype, proto)
            connection.settimeout(timeout)
            phase_started = timer()
            try:
                connection.connect(sockaddr)
            finally:
                connect_ms = _ms(phase_started)

            if parts.scheme == "https":
                context = ssl.create_default_context()
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                phase_started = timer()
                connection = context.wrap_socket(connection, server_hostname=hostname)
                tls_ms = _ms(phase_started)

            path = parts.path or "/"
            if parts.query:
                path = f"{path}?{parts.query}"
            host = hostname
            if ":" in host:
                host = f"[{host}]"
            if port != default_port:
                host = f"{host}:{port}"
            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                "Cache-Control: no-cache\r\n"
                "Connection: close\r\n"
                f"User-Agent: lupaxa-time-to-first-byte/{get_version()}\r\n"
                "\r\n"
            ).encode("ascii")
            connection.sendall(request)

            response = connection.recv(4096)
            if not response:
                raise OSError("incomplete response")
            ttfb_ms = _ms(sample_started)
            while b"\r\n" not in response:
                chunk = connection.recv(4096)
                if not chunk:
                    raise OSError("incomplete response")
                response += chunk
            status_line = response.split(b"\r\n", 1)[0]
            try:
                status = int(status_line.split(b" ", 2)[1])
            except (IndexError, ValueError) as exc:
                raise OSError("incomplete response") from exc

            if status not in _REDIRECT_STATUSES:
                return build_result(
                    True,
                    DETAIL_OK,
                    dns_ms,
                    connect_ms,
                    tls_ms,
                    ttfb_ms,
                    status,
                    redirects,
                    current_url,
                )

            while b"\r\n\r\n" not in response:
                chunk = connection.recv(4096)
                if not chunk:
                    raise OSError("incomplete response")
                response += chunk
            location = None
            header_block = response.split(b"\r\n\r\n", 1)[0]
            for line in header_block.split(b"\r\n")[1:]:
                name, separator, value = line.partition(b":")
                if separator and name.lower() == b"location":
                    location = value.strip().decode("latin-1")
                    break
            if location is None:
                return build_result(
                    False,
                    DETAIL_NO_LOCATION,
                    dns_ms,
                    connect_ms,
                    tls_ms,
                    None,
                    status,
                    redirects,
                    current_url,
                )
            if redirects >= max_redirects:
                return build_result(
                    False,
                    DETAIL_TOO_MANY,
                    dns_ms,
                    connect_ms,
                    tls_ms,
                    None,
                    status,
                    redirects,
                    current_url,
                )
            current_url = urljoin(current_url, location)
            redirects += 1
            redirect_parts = urlsplit(current_url)
            if redirect_parts.scheme not in {"http", "https"}:
                return build_result(
                    False,
                    f"{DETAIL_OS_ERROR_PREFIX}redirect scheme must be http or https",
                    dns_ms,
                    connect_ms,
                    tls_ms,
                    None,
                    status,
                    redirects,
                    current_url,
                )
            try:
                _ = redirect_parts.port
            except ValueError:
                return build_result(
                    False,
                    f"{DETAIL_OS_ERROR_PREFIX}invalid port in URL",
                    dns_ms,
                    connect_ms,
                    tls_ms,
                    None,
                    status,
                    redirects,
                    current_url,
                )
        except socket.gaierror:
            detail = DETAIL_DNS
        except TimeoutError:
            detail = DETAIL_TIMEOUT
        except ConnectionRefusedError:
            detail = DETAIL_REFUSED
        except ssl.SSLError:
            detail = DETAIL_TLS
        except OSError as exc:
            detail = f"{DETAIL_OS_ERROR_PREFIX}{exc}"
        finally:
            if connection is not None:
                connection.close()
        if detail is not None:
            return build_result(
                False,
                detail,
                dns_ms,
                connect_ms,
                tls_ms,
                None,
                status,
                redirects,
                current_url,
            )


def summarize(results: list[TimingResult] | tuple[TimingResult, ...]) -> TimingSummary:
    """Build a summary from collected samples.

    Min, average, and max use passing samples only. They are ``None``
    when every sample failed or the list is empty.
    """
    collected = tuple(results)
    total = len(collected)
    passed_times = [item.ttfb_ms for item in collected if item.ok]
    passed = len(passed_times)
    failed = total - passed
    fail_percent = 0.0 if total == 0 else failed / total * 100
    ttfb_min: float | None
    ttfb_max: float | None
    ttfb_avg: float | None
    if passed_times:
        ttfb_min = min(passed_times)
        ttfb_max = max(passed_times)
        ttfb_avg = sum(passed_times) / passed
    else:
        ttfb_min = ttfb_max = ttfb_avg = None
    return TimingSummary(
        total=total,
        passed=passed,
        failed=failed,
        fail_percent=fail_percent,
        ttfb_min_ms=ttfb_min,
        ttfb_avg_ms=ttfb_avg,
        ttfb_max_ms=ttfb_max,
        results=collected,
    )


def run_measurements(
    url: str,
    *,
    delay: float = DEFAULT_DELAY,
    timeout: float = DEFAULT_TIMEOUT,
    count: int | None = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    on_result: Callable[[TimingResult], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> TimingSummary:
    """Measure a URL once, ``count`` times, or until stopped.

    Parameters
    ----------
    url
        HTTP or HTTPS URL to measure.
    delay
        Seconds to wait between samples. Must be ``0`` or greater.
    timeout
        Socket timeout in seconds. Must be greater than ``0``.
    count
        Number of samples. ``None`` means run until ``should_stop``
        returns true, or forever if it is omitted.
    max_redirects
        Maximum redirects to follow for each sample.
    on_result
        Optional callback invoked after each sample.
    should_stop
        Optional predicate checked before each sample and before each
        inter-sample sleep.

    Returns
    -------
    TimingSummary
        Totals for every sample that ran.

    Raises
    ------
    ValueError
        If ``delay`` is not finite and ``>= 0``, or ``count`` is not
        ``None`` and is less than ``1``.
    """
    delay = _require_delay(delay)
    count = _require_count(count)

    results: list[TimingResult] = []
    sequence = 0
    while count is None or sequence < count:
        if should_stop is not None and should_stop():
            break
        result = measure(
            url,
            timeout=timeout,
            sequence=sequence,
            max_redirects=max_redirects,
        )
        results.append(result)
        if on_result is not None:
            on_result(result)
        sequence += 1
        if count is not None and sequence >= count:
            break
        if should_stop is not None and should_stop():
            break
        time.sleep(delay)
    return summarize(results)
