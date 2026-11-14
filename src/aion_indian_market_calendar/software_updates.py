"""Explicit, operator-approved software version discovery. Never installs code.

The SHA-256 of the approval manifest is supplied through a trusted operator
channel, independently of its download. A checksum fetched beside an arbitrary
artifact is not an approval. No discovery is performed on import or calendar use.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.metadata import version as installed_version
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

PROJECT = "aion-indian-market-calendar"
MAX_MANIFEST_BYTES = 128 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024


def release_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value):
        raise ValueError("Only approved stable x.y.z releases are supported")
    return tuple(int(n) for n in value.split("."))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Update redirects are refused; approve the final destination explicitly")


def fetch_bytes(url: str, *, max_bytes: int, network_authorized: bool = False,
                allow_test_http: bool = False) -> bytes:
    """One bounded HTTPS request, no redirects, proxy, identifier or retry loop."""
    from .store import _offline
    u = urlsplit(url)
    if not network_authorized or _offline():
        raise PermissionError("Explicit network approval and online policy are required")
    test = allow_test_http and u.scheme == "http" and u.hostname == "127.0.0.1"
    if not (u.scheme == "https" or test) or not u.hostname or u.username or u.password or u.fragment:
        raise ValueError("Updates require a credential-free HTTPS destination")
    from urllib.request import ProxyHandler
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(Request(url, headers={"User-Agent": "aion-calendar-updater"}), timeout=5) as response:
        import time
        deadline = time.monotonic() + 10
        chunks = []
        size = 0
        while size <= max_bytes:
            if time.monotonic() > deadline:
                raise TimeoutError("Update transfer exceeded its wall-clock budget")
            chunk = response.read1(min(64 * 1024, max_bytes + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        data = b"".join(chunks)
    if len(data) > max_bytes:
        raise ValueError("Update resource exceeds its size limit")
    return data


@dataclass(frozen=True)
class ReleaseOffer:
    installed: str
    available: str
    newer: bool
    manifest_sha256: str
    manifest: dict


def verify_approval(raw: bytes, expected_sha256: str, *, current_version: str | None = None) -> ReleaseOffer:
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Approval manifest too large")
    digest = hashlib.sha256(raw).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or digest != expected_sha256:
        raise ValueError("Approval manifest hash mismatch")
    doc = json.loads(raw)
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or doc.get("project") != PROJECT:
        raise ValueError("Unsupported software approval contract")
    if doc.get("approved") is not True or not doc.get("approval_id"):
        raise ValueError("Release has no explicit operator approval")
    target = doc.get("version")
    release_tuple(target)
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts or len(artifacts) > 16:
        raise ValueError("Approval must enumerate its bounded wheel closure")
    names = set()
    project_wheels = 0
    for item in artifacts:
        name = item.get("filename", "")
        if not isinstance(name, str) or Path(name).name != name or not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", name) or name in names:
            raise ValueError("Invalid or duplicate wheel filename")
        names.add(name)
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise ValueError("Every wheel needs an approved SHA-256")
        if type(item.get("size")) is not int or not 0 < item["size"] <= MAX_ARTIFACT_BYTES:
            raise ValueError("Every wheel needs a bounded exact size")
        if name.startswith("aion_indian_market_calendar-"):
            if not name.startswith(f"aion_indian_market_calendar-{target}-"):
                raise ValueError("Calendar wheel version differs from approval")
            project_wheels += 1
    if project_wheels != 1:
        raise ValueError("Exactly one approved calendar wheel is required")
    current = current_version or installed_version(PROJECT)
    return ReleaseOffer(current, target, release_tuple(target) > release_tuple(current), digest, doc)


def discover(url: str, *, approved_manifest_sha256: str, network_authorized: bool = False,
             current_version: str | None = None, allow_test_http: bool = False) -> ReleaseOffer:
    raw = fetch_bytes(url, max_bytes=MAX_MANIFEST_BYTES, network_authorized=network_authorized,
                      allow_test_http=allow_test_http)
    return verify_approval(raw, approved_manifest_sha256, current_version=current_version)
