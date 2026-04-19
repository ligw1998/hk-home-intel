from __future__ import annotations

import subprocess
from typing import Any

import httpx

from hk_home_intel_shared.settings import get_settings


DEFAULT_HEADERS = {
    "User-Agent": "HK-Home-Intel/0.1 (+local research workstation)",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}
CURL_MIN_TIMEOUT = 30.0
CURL_TIMEOUT_RETRIES = 1


def create_client(*, timeout: float = 60.0, headers: dict[str, str] | None = None) -> httpx.Client:
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    settings = get_settings()
    return httpx.Client(
        headers=request_headers,
        follow_redirects=True,
        timeout=timeout,
        trust_env=settings.http_trust_env,
    )


def fetch_text(url: str, timeout: float = 20.0) -> str:
    try:
        with create_client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError:
        return _fetch_text_with_curl(url, timeout=max(timeout, CURL_MIN_TIMEOUT))


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> Any:
    with create_client(timeout=timeout, headers=headers) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def post_bytes(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float = 60.0,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, dict[str, str], int]:
    with create_client(timeout=timeout, headers=headers) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.content, dict(response.headers), response.status_code


def _fetch_text_with_curl(url: str, timeout: float) -> str:
    attempts = CURL_TIMEOUT_RETRIES + 1
    for attempt in range(attempts):
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-L",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    str(int(timeout)),
                    "-A",
                    DEFAULT_HEADERS["User-Agent"],
                    "-H",
                    f"Accept: {DEFAULT_HEADERS['Accept']}",
                    url,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 28 and attempt + 1 < attempts:
                continue
            raise
    raise RuntimeError("unreachable curl fetch retry state")
