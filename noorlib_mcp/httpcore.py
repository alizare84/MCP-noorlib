"""Shared async HTTP core for the lighter Noor-family clients.

Implements the same proven policies as noorlib_mcp.client /
hadith_client:

* ambient http_proxy is IGNORED by default (NOORLIB_MCP_USE_PROXY=1
  opts in) — broken local proxies must not break the server
* per-host throttle + retry on 429/5xx
* full exception text in every error (type + message)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"


def _use_proxy() -> bool:
    return os.environ.get("NOORLIB_MCP_USE_PROXY", "").strip() in (
        "1", "true", "TRUE", "yes",
    )


class SiteError(RuntimeError):
    pass


class SiteClient:
    """Throttled, retrying JSON client for one Noor-family host."""

    name = "site"

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        throttle: float = 1.2,
        retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.throttle = throttle
        self.retries = retries
        base_headers = {
            "User-Agent": _UA,
            "Accept": "application/json, text/plain, */*",
        }
        if headers:
            base_headers.update(headers)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=base_headers,
            timeout=timeout,
            trust_env=_use_proxy(),
            verify=True,
            follow_redirects=True,
        )
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ plumbing
    async def _throttle(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self.throttle - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

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
        for attempt in range(1, self.retries + 1):
            await self._throttle()
            try:
                if method == "POST":
                    resp = await self._client.post(
                        path, json=payload, params=params, headers=headers
                    )
                else:
                    resp = await self._client.get(
                        path, params=params, headers=headers
                    )
            except httpx.HTTPError as exc:
                raise SiteError(
                    f"[{self.name}] network error calling {method} {path} "
                    f"(attempt {attempt}/{self.retries}): "
                    f"{type(exc).__name__}: {exc} — hint: this client "
                    f"ignores http_proxy unless NOORLIB_MCP_USE_PROXY=1"
                ) from exc

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                last_body = resp.text[:300]
                await asyncio.sleep(min(2.0 * attempt, 6.0))
                continue
            if resp.status_code != 200:
                raise SiteError(
                    f"[{self.name}] HTTP {resp.status_code} from {path}: "
                    f"{resp.text[:300]}"
                )
            try:
                return resp.json()
            except ValueError as exc:
                raise SiteError(
                    f"[{self.name}] non-JSON response from {path}: "
                    f"{resp.text[:300]}"
                ) from exc

        raise SiteError(
            f"[{self.name}] request failed after {self.retries} attempts "
            f"calling {path}; last body: {last_body}"
        )

    async def get(self, path: str, **kw: Any) -> Any:
        return await self._request("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self._request("POST", path, **kw)

    async def close(self) -> None:
        await self._client.aclose()
