"""
Optional Cloudflare R2 storage for uploaded stimuli (S3-compatible, no egress fees).

Enabled when R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET
are all set. The bucket stays private: the browser uploads through a presigned
PUT URL that binds the declared type and size, and stimuli are stored as
``r2:<object key>`` references that the API turns into presigned GET URLs each
time it returns them. Requests are signed with AWS Signature Version 4, written
out here with the standard library.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import os
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import quote
from xml.sax.saxutils import escape

REF_PREFIX = "r2:"
REGION = "auto"
SERVICE = "s3"
UPLOAD_URL_SECONDS = 15 * 60
READ_URL_SECONDS = 24 * 60 * 60


class R2RequestError(RuntimeError):
    """R2 rejected or did not answer a request."""


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def r2_configured() -> bool:
    return all(_env(n) for n in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"))


def _host() -> str:
    return f"{_env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"


def _uri(key: str) -> str:
    return "/" + quote(_env("R2_BUCKET"), safe="") + "/" + quote(key, safe="/~")


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date: str, region: str, service: str) -> bytes:
    k = _hmac(("AWS4" + secret).encode("utf-8"), date)
    k = _hmac(k, region)
    k = _hmac(k, service)
    return _hmac(k, "aws4_request")


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(
        f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(params.items())
    )


def presign(
    method: str,
    host: str,
    uri: str,
    access_key: str,
    secret_key: str,
    expires: int,
    now: _dt.datetime,
    region: str = REGION,
    service: str = SERVICE,
    extra_headers: Optional[dict[str, str]] = None,
) -> str:
    """Presigned URL (SigV4 query authentication) for *method* on ``https://host + uri``."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    headers = {"host": host, **{k.lower(): v.strip() for k, v in (extra_headers or {}).items()}}
    signed_headers = ";".join(sorted(headers))
    scope = f"{date}/{region}/{service}/aws4_request"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": signed_headers,
    }
    canonical = "\n".join([
        method,
        uri,
        _canonical_query(params),
        "".join(f"{k}:{headers[k]}\n" for k in sorted(headers)),
        signed_headers,
        "UNSIGNED-PAYLOAD",
    ])
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    signature = hmac.new(_signing_key(secret_key, date, region, service), to_sign.encode(), hashlib.sha256).hexdigest()
    return f"https://{host}{uri}?{_canonical_query(params)}&X-Amz-Signature={signature}"


def authorization_headers(
    method: str,
    host: str,
    uri: str,
    query: str,
    body: bytes,
    access_key: str,
    secret_key: str,
    now: _dt.datetime,
    region: str = REGION,
    service: str = SERVICE,
    extra_headers: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Headers (including Authorization) for a SigV4 header-authenticated request."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        **{k.lower(): v.strip() for k, v in (extra_headers or {}).items()},
    }
    signed_headers = ";".join(sorted(headers))
    scope = f"{date}/{region}/{service}/aws4_request"
    canonical = "\n".join([
        method,
        uri,
        query,
        "".join(f"{k}:{headers[k]}\n" for k in sorted(headers)),
        signed_headers,
        payload_hash,
    ])
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    signature = hmac.new(_signing_key(secret_key, date, region, service), to_sign.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    )
    return headers


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def create_upload_url(key: str, content_type: str, size_bytes: int) -> str:
    """One presigned PUT for *key*; R2 rejects the upload if its type or size differ from the declared ones."""
    return presign(
        "PUT", _host(), _uri(key), _env("R2_ACCESS_KEY_ID"), _env("R2_SECRET_ACCESS_KEY"),
        UPLOAD_URL_SECONDS, _now(),
        extra_headers={"content-type": content_type, "content-length": str(size_bytes)},
    )


def read_url(key: str) -> str:
    return presign("GET", _host(), _uri(key), _env("R2_ACCESS_KEY_ID"), _env("R2_SECRET_ACCESS_KEY"),
                   READ_URL_SECONDS, _now())


def ref_for(key: str) -> str:
    return REF_PREFIX + key


def resolve_ref(url: Optional[str]) -> Optional[str]:
    """Turn an ``r2:<key>`` reference into a presigned GET URL; leave every other value unchanged."""
    if not url or not url.startswith(REF_PREFIX) or not r2_configured():
        return url
    return read_url(url[len(REF_PREFIX):])


def delete_keys(keys: list[str]) -> dict[str, object]:
    """Delete objects with one DeleteObjects request per 1,000 keys (missing keys are not an error)."""
    unique = sorted({k for k in keys if k})
    if not unique:
        return {"status": "noop", "deleted": []}
    if not r2_configured():
        return {"status": "skipped_unconfigured", "deleted": [], "paths": unique}
    deleted: list[str] = []
    for start in range(0, len(unique), 1000):
        chunk = unique[start:start + 1000]
        body = ("<Delete><Quiet>true</Quiet>" + "".join(
            f"<Object><Key>{escape(k)}</Key></Object>" for k in chunk) + "</Delete>").encode("utf-8")
        md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
        uri = "/" + quote(_env("R2_BUCKET"), safe="") + "/"
        headers = authorization_headers(
            "POST", _host(), uri, "delete=", body, _env("R2_ACCESS_KEY_ID"), _env("R2_SECRET_ACCESS_KEY"), _now(),
            extra_headers={"content-md5": md5, "content-type": "application/xml"},
        )
        headers.pop("host")
        request = urllib.request.Request(f"https://{_host()}{uri}?delete", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30):
                deleted.extend(chunk)
        except urllib.error.HTTPError as exc:
            return {"status": "error", "deleted": deleted, "paths": unique, "http_status": exc.code,
                    "detail": exc.read().decode("utf-8", errors="replace")[:500]}
        except (urllib.error.URLError, TimeoutError) as exc:
            return {"status": "error", "deleted": deleted, "paths": unique, "detail": str(exc)}
    return {"status": "deleted", "deleted": deleted, "paths": unique}
