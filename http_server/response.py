"""
HTTP/1.1 response construction.

Builds well-formed responses by hand (status line, headers, body) so the
server controls exactly what goes over the wire — including the headers
that make keep-alive and caching actually work.
"""

from __future__ import annotations

from datetime import datetime, timezone

STATUS_TEXT = {
    200: "OK",
    206: "Partial Content",
    304: "Not Modified",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    413: "Payload Too Large",
    431: "Request Header Fields Too Large",
    500: "Internal Server Error",
    505: "HTTP Version Not Supported",
}

SERVER_NAME = "PySocketServer/1.0"


def http_date(dt: datetime | None = None) -> str:
    """RFC 7231 IMF-fixdate, e.g. 'Fri, 03 Jul 2026 12:00:00 GMT'."""
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


class HTTPResponse:
    def __init__(self, status: int, body: bytes = b"", headers: dict | None = None):
        self.status = status
        self.body = body
        self.headers = headers or {}

    def to_bytes(self, *, keep_alive: bool, include_body: bool = True) -> bytes:
        reason = STATUS_TEXT.get(self.status, "Unknown")
        lines = [f"HTTP/1.1 {self.status} {reason}"]

        headers = dict(self.headers)
        headers.setdefault("Date", http_date())
        headers.setdefault("Server", SERVER_NAME)
        headers.setdefault("Content-Length", str(len(self.body)))
        headers["Connection"] = "keep-alive" if keep_alive else "close"

        for name, value in headers.items():
            lines.append(f"{name}: {value}")
        lines.append("")  # blank line ends the headers
        lines.append("")  # trailing CRLF after body separator

        head = "\r\n".join(lines).encode("iso-8859-1")
        return head + (self.body if include_body else b"")

    # --- convenience constructors -----------------------------------

    @classmethod
    def error(cls, status: int, message: str = "") -> "HTTPResponse":
        reason = STATUS_TEXT.get(status, "Unknown")
        text = message or reason
        body = (
            f"<html><head><title>{status} {reason}</title></head>"
            f"<body><h1>{status} {reason}</h1><p>{text}</p></body></html>"
        ).encode("utf-8")
        return cls(status, body, {"Content-Type": "text/html; charset=utf-8"})
