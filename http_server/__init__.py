"""
A from-scratch HTTP/1.1 web server built directly on top of TCP sockets.

No frameworks (no Flask, no http.server) — this package implements the
socket handling, HTTP parsing, and response generation itself, in order
to demonstrate a solid understanding of the protocol and of networked,
concurrent systems programming.
"""

from .server import HTTPServer
from .request import HTTPRequest, HTTPParseError
from .response import HTTPResponse

__all__ = ["HTTPServer", "HTTPRequest", "HTTPParseError", "HTTPResponse"]
