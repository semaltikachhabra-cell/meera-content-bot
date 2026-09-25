"""Tiny JSON-over-HTTP helper using only the standard library (no dependencies to install)."""
import json
import time
import urllib.error
import urllib.request


class HttpError(Exception):
    pass


def request(method, url, headers=None, body=None, timeout=45, retries=1):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            # Retry once on rate limits / temporary overload.
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2)
                continue
            raise HttpError(f"{method} {url.split('?')[0]} -> {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2)
                continue
            raise HttpError(f"{method} {url.split('?')[0]} -> {e.reason}") from None


def get_bytes(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()
