"""Public URL/Google Drive ingestion with SSRF and download-size protections."""
from __future__ import annotations

import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

from ..config import get_settings


class URLFetchError(ValueError):
    pass


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise URLFetchError("Enter a valid public HTTP or HTTPS document URL.")
    if parsed.username or parsed.password:
        raise URLFetchError("URLs containing credentials are not allowed.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise URLFetchError("The document host could not be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise URLFetchError("Private or local network URLs are not allowed.")


def normalize_google_drive_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname not in {"drive.google.com", "docs.google.com"}:
        return url
    match = re.search(r"/d/([A-Za-z0-9_-]+)", parsed.path)
    file_id = match.group(1) if match else parse_qs(parsed.query).get("id", [None])[0]
    if not file_id:
        raise URLFetchError("The Google Drive file ID could not be detected. Use a public file-sharing link.")
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _filename_from_headers(response: httpx.Response, url: str) -> str:
    disposition = response.headers.get("content-disposition", "")
    utf = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
    plain = re.search(r'filename="?([^";]+)', disposition, re.I)
    if utf:
        return Path(unquote(utf.group(1))).name
    if plain:
        return Path(plain.group(1).strip()).name
    name = Path(urlparse(url).path).name
    return name or "public-document"


def fetch_public_document(url: str, destination_dir: Path) -> tuple[Path, str, str, int]:
    settings = get_settings()
    current = normalize_google_drive_url(url.strip())
    headers = {"User-Agent": "NIET-AI-QPG/1.0 (academic document fetcher)"}
    with httpx.Client(timeout=httpx.Timeout(30, connect=10), headers=headers, follow_redirects=False) as client:
        response = None
        for _ in range(6):
            _assert_public_url(current)
            response = client.send(client.build_request("GET", current), stream=True)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                response.close()
                if not location:
                    raise URLFetchError("The document link returned an invalid redirect.")
                current = urljoin(current, location)
                continue
            break
        else:
            raise URLFetchError("The document link redirected too many times.")

        if response is None or response.status_code in {401, 403}:
            if response:
                response.close()
            raise URLFetchError("This document is private or requires authentication. Make it publicly viewable and try again.")
        if response.status_code >= 400:
            response.close()
            raise URLFetchError(f"The document server returned HTTP {response.status_code}.")
        content_length = int(response.headers.get("content-length", "0") or 0)
        if content_length > settings.url_fetch_max_bytes:
            response.close()
            raise URLFetchError("The remote document exceeds the configured size limit.")
        content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0].strip().lower()
        filename = _filename_from_headers(response, current)
        content = bytearray()
        for chunk in response.iter_bytes(1024 * 1024):
            content.extend(chunk)
            if len(content) > settings.url_fetch_max_bytes:
                response.close()
                raise URLFetchError("The remote document exceeds the configured size limit.")
        response.close()

    content = bytes(content)
    extension = Path(filename).suffix.lower()
    mime_extensions = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "text/plain": ".txt", "text/csv": ".csv", "text/html": ".html",
        "image/png": ".png", "image/jpeg": ".jpg", "image/tiff": ".tiff",
    }
    if not extension:
        extension = mime_extensions.get(content_type, "")
        filename += extension
    # Drive permission/interstitial pages are HTML and must not masquerade as a document.
    if "drive.google.com" in current and content_type == "text/html":
        raise URLFetchError("Google Drive did not return a public downloadable file. Check sharing permissions.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    destination.write_bytes(content)
    return destination, filename, content_type, len(content)
