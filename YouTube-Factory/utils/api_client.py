"""Unified async HTTP client for API calls."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class APIClient:
    """Async HTTP client with retry logic and rate limiting."""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = 120.0,
        max_retries: int = 3,
        rate_limit_per_minute: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(rate_limit_per_minute)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        data: Any = None,
        files: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an API request with retry and rate limiting."""
        async with self._semaphore:
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    client = await self._get_client()
                    response = await client.request(
                        method=method,
                        url=path,
                        json=json,
                        data=data,
                        files=files,
                        params=params,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    last_error = e
                    if e.response.status_code == 429:
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"Rate limited. Waiting {wait}s...")
                        await asyncio.sleep(wait)
                    elif e.response.status_code >= 500:
                        wait = 2 ** attempt
                        logger.warning(f"Server error {e.response.status_code}. Retry in {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        raise
                except (httpx.ConnectError, httpx.ReadTimeout) as e:
                    last_error = e
                    wait = 2 ** attempt
                    logger.warning(f"Connection error: {e}. Retry in {wait}s")
                    await asyncio.sleep(wait)

            raise RuntimeError(f"API request failed after {self.max_retries} attempts: {last_error}")

    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("PUT", path, **kwargs)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
