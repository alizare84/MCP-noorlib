"""Shared async HTTP core for the Noor-family clients.

Policies (shared by every site client):

* transient network errors ARE retried (timeouts, connect/reset, protocol
  errors) — not only 429/5xx
* 429/5xx retried with Retry-After + jitter; NO pointless sleep after the
  last attempt
* per-host throttle: requests are spaced by `throttle` seconds WITHOUT
  holding the lock during the sleep (no head-of-line blocking)
* ambient http_proxy is IGNORED by default; opt in with
  NOORLIB_MCP_USE_PROXY=1 (or NOOR_MCP_USE_PROXY=1)
* corporate CA bundles: NOORLIB_MCP_CA_BUNDLE=/path/to/ca.pem
* base_url must be https://
* User-Agent override: NOORLIB_MCP_UA (default keeps a browser UA because
  some endpoints reject unknown clients)
* subclasses customize `error` (exception class) and `_after_json()`
  (per-site API status conventions)
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any

import httpx

_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"


def _use_proxy() -> bool:
    for key in ("NOOR_MCP_USE_PROXY", "NOORLIB_MCP_USE_PROXY"):
        if os.environ.get(key, "").strip().lower() in ("1", "true", "yes"):
            return True
    return False


class SiteError(RuntimeError):
    """Any failure while talking to a Noor-family site."""


class SiteClient:
    """Throttled, retrying JSON client for one Noor-family host."""

    name = "site"
    error = SiteError

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        throttle: float = 1.2,
        retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        if not str(base_url).startswith("https://"):
            raise ValueError(f"[{self.name}] base_url must start with https:// — got {base_url!r}")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.throttle = throttle
        self.retries = retries
        ua = os.environ.get("NOORLIB_MCP_UA", "").strip() or _UA
        base_headers = {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
        }
        if headers:
            base_headers.update(headers)
        ca_bundle = os.environ.get("NOORLIB_MCP_CA_BUNDLE", "").strip()
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=base_headers,
            timeout=timeout,
            trust_env=_use_proxy(),
            verify=ca_bundle or True,
            follow_redirects=True,
        )
        self._next_slot = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ plumbing
    async def _throttle(self) -> None:
        """Reserve a slot spaced by `throttle` seconds; lock is never held
        while sleeping, so concurrent callers queue fairly without blocking
        the event loop."""
        while True:
            async with self._lock:
                now = time.monotonic()
                wait = self._next_slot - now
                if wait <= 0:
                    self._next_slot = max(now, self._next_slot) + self.throttle
                    return
            await asyncio.sleep(min(wait, 5.0))

    async def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = min(2.0 * attempt, 6.0)
        if retry_after:
            try:
                delay = max(delay, min(float(retry_after), 10.0))
            except ValueError:
                pass
        await asyncio.sleep(delay + random.uniform(0.0, 0.5))

    def _proxy_hint(self, exc: Exception) -> str:
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            return (
                " — hint: if a local proxy breaks the connection, this client "
                "ignores http_proxy unless NOORLIB_MCP_USE_PROXY=1"
            )
        return ""

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        payload: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        last_body = ""
        last_exc: Exception | None = None

        for attempt in range(1, self.retries + 1):
            await self._throttle()
            try:
                if method == "POST":
                    resp = await self._client.post(
                        path, json=payload, params=params, headers=headers
                    )
                else:
                    resp = await self._client.get(path, params=params, headers=headers)
            except httpx.TransportError as exc:
                # timeouts, connect/reset/TLS-transport failures: retryable
                last_exc = exc
                if attempt >= self.retries:
                    raise self.error(
                        f"[{self.name}] network error calling {method} {path} "
                        f"(attempt {attempt}/{self.retries}): "
                        f"{type(exc).__name__}: {exc}{self._proxy_hint(exc)}"
                    ) from exc
                await self._backoff(attempt)
                continue
            except httpx.HTTPError as exc:
                # non-transport misuse (bad URL, invalid request): not retryable
                raise self.error(f"[{self.name}] {type(exc).__name__}: {exc}") from exc

            status = resp.status_code
            if status == 429 or 500 <= status < 600:
                last_body = resp.text[:200]
                last_exc = self.error(
                    f"[{self.name}] HTTP {status} on attempt {attempt}/{self.retries}"
                )
                if attempt >= self.retries:
                    break  # no pointless sleep on the final attempt
                await self._backoff(attempt, resp.headers.get("Retry-After"))
                continue
            if status != 200:
                raise self.error(
                    f"[{self.name}] HTTP {status} from {path}: "
                    f"«بدنه‌ی نامعتبر از سایت» {resp.text[:200]}"
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise self.error(
                    f"[{self.name}] non-JSON response from {path}: "
                    f"«بدنه‌ی نامعتبر از سایت» {resp.text[:200]}"
                ) from exc
            return self._after_json(data, path)

        raise self.error(
            f"[{self.name}] request failed after {self.retries} attempts "
            f"calling {path}; last error: {last_exc}; "
            f"last body «بدنه‌ی نامعتبر از سایت»: {last_body}"
        )

    def _after_json(self, data: Any, path: str) -> Any:
        """Per-site hook: validate API-level status conventions."""
        return data

    async def get(self, path: str, **kw: Any) -> Any:
        return await self._request("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self._request("POST", path, **kw)

    async def close(self) -> None:
        await self._client.aclose()
