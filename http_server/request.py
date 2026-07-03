"""
HTTP/1.1 request parsing.

Reads a raw request directly off a socket and turns it into a structured
HTTPRequest object: method, path, query string, HTTP version, headers,
and body. Handles the framing rules HTTP/1.1 actually requires (reading
until the blank line that ends the headers, then respecting
Content-Length for the body) rather than assuming a single recv() call
returns a complete request.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit, parse_qs

MAX_HEADER_BYTES = 64 * 1024      # guard against unbounded header floods
MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB cap on request bodies
RECV_CHUNK = 4096


class HTTPParseError(Exception):
    """Raised when a request is malformed. Caller should reply 400."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class HTTPRequest:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    version: str = "HTTP/1.1"
    headers: dict = field(default_factory=dict)
    body: bytes = b""

    @property
    def keep_alive(self) -> bool:
        """HTTP/1.1 defaults to persistent connections unless told otherwise."""
        connection = self.headers.get("connection", "").lower()
        if connection == "close":
            return False
        if connection == "keep-alive":
            return True
        # No explicit header: HTTP/1.1 -> keep-alive, HTTP/1.0 -> close
        return self.version == "HTTP/1.1"

    @classmethod
    def from_socket(cls, conn: socket.socket) -> "HTTPRequest":
        """
        Read exactly one HTTP request off `conn`. Blocks (subject to the
        socket's configured timeout) until either a full request has
        arrived or the connection is closed/times out.
        """
        buf = b""

        # --- Read until we have the full header block (CRLFCRLF) ---
        while b"\r\n\r\n" not in buf:
            if len(buf) > MAX_HEADER_BYTES:
                raise HTTPParseError(431, "Request header fields too large")
            chunk = conn.recv(RECV_CHUNK)
            if not chunk:
                if buf:
                    raise HTTPParseError(400, "Connection closed mid-request")
                raise ConnectionClosed()  # clean close between requests
            buf += chunk

        head, _, rest = buf.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        if not lines or not lines[0]:
            raise HTTPParseError(400, "Empty request line")

        request_line = lines[0].decode("iso-8859-1", errors="replace")
        parts = request_line.split(" ")
        if len(parts) != 3:
            raise HTTPParseError(400, "Malformed request line")
        method, raw_target, version = parts

        if version not in ("HTTP/1.0", "HTTP/1.1"):
            raise HTTPParseError(505, "HTTP Version Not Supported")

        split = urlsplit(raw_target)
        path = split.path or "/"
        query = {k: v[0] for k, v in parse_qs(split.query).items()}

        headers = {}
        for line in lines[1:]:
            if not line:
                continue
            name, sep, value = line.decode("iso-8859-1", errors="replace").partition(":")
            if not sep:
                raise HTTPParseError(400, f"Malformed header: {line!r}")
            headers[name.strip().lower()] = value.strip()

        # Host header is mandatory in HTTP/1.1 (RFC 7230 §5.4)
        if version == "HTTP/1.1" and "host" not in headers:
            raise HTTPParseError(400, "Missing Host header")

        # --- Read the body, if any, based on Content-Length ---
        body = rest
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                raise HTTPParseError(400, "Invalid Content-Length")
            if length > MAX_BODY_BYTES:
                raise HTTPParseError(413, "Payload too large")
            while len(body) < length:
                chunk = conn.recv(min(RECV_CHUNK, length - len(body)))
                if not chunk:
                    raise HTTPParseError(400, "Connection closed mid-body")
                body += chunk
            body = body[:length]
        # (Chunked transfer-encoding intentionally out of scope for this
        #  build — see README for what a "maximal" version would add.)

        return cls(
            method=method,
            path=path,
            query=query,
            version=version,
            headers=headers,
            body=body,
        )


class ConnectionClosed(Exception):
    """The peer closed the connection cleanly before sending a new request."""
