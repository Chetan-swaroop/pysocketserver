"""
Request -> Response logic: serves static files out of a document root.

Security and correctness details this handles explicitly:
  * Path traversal protection ("..", absolute paths, symlink escapes)
  * Correct MIME type per file extension
  * Conditional GET via Last-Modified / If-Modified-Since -> 304
  * HEAD support (same headers as GET, no body)
  * 405 for unsupported methods, with an Allow header
"""

from __future__ import annotations

import mimetypes
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .request import HTTPRequest
from .response import HTTPResponse, http_date

mimetypes.init()
DEFAULT_MIME = "application/octet-stream"


class StaticFileHandler:
    def __init__(self, doc_root: str):
        self.doc_root = os.path.realpath(doc_root)

    def handle(self, request: HTTPRequest) -> HTTPResponse:
        if request.method not in ("GET", "HEAD"):
            resp = HTTPResponse.error(405, "Only GET and HEAD are supported")
            resp.headers["Allow"] = "GET, HEAD"
            return resp

        try:
            file_path = self._resolve_path(request.path)
        except PermissionError:
            return HTTPResponse.error(403, "Forbidden")

        if file_path is None or not os.path.isfile(file_path):
            return HTTPResponse.error(404, "The requested resource was not found")

        return self._serve_file(file_path, request, send_body=request.method == "GET")

    # ------------------------------------------------------------------

    def _resolve_path(self, url_path: str) -> str | None:
        """
        Map a URL path to a real filesystem path, refusing anything that
        would escape doc_root (e.g. '/../../etc/passwd').
        """
        if url_path == "/":
            url_path = "/index.html"

        # Strip leading slashes and normalize; reject any ".." component
        # explicitly rather than relying solely on realpath, since that
        # gives a clearer signal before we even touch the filesystem.
        parts = [p for p in url_path.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise PermissionError("path traversal attempt")

        candidate = os.path.realpath(os.path.join(self.doc_root, *parts))

        # Defense in depth: even after normalization, confirm the
        # resolved path is still inside doc_root (catches symlink tricks).
        if os.path.commonpath([candidate, self.doc_root]) != self.doc_root:
            raise PermissionError("resolved path escapes doc_root")

        return candidate

    def _serve_file(self, path: str, request: HTTPRequest, send_body: bool) -> HTTPResponse:
        stat = os.stat(path)
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        if_modified_since = request.headers.get("if-modified-since")
        if if_modified_since:
            try:
                since = parsedate_to_datetime(if_modified_since)
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
                if last_modified.replace(microsecond=0) <= since:
                    return HTTPResponse(304, b"", {"Last-Modified": http_date(last_modified)})
            except (TypeError, ValueError):
                pass  # malformed header -> just serve the file normally

        content_type, _ = mimetypes.guess_type(path)
        content_type = content_type or DEFAULT_MIME

        with open(path, "rb") as f:
            body = f.read() if send_body else b""

        headers = {
            "Content-Type": content_type,
            "Content-Length": str(stat.st_size),
            "Last-Modified": http_date(last_modified),
            "Cache-Control": "public, max-age=60",
        }
        return HTTPResponse(200, body, headers)
