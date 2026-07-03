"""
The TCP server itself: listens for connections, hands each one to a
worker thread, and drives the request/response loop (including
HTTP/1.1 keep-alive) for that connection.

Concurrency model: a bounded ThreadPoolExecutor. Threads (not raw
os.fork or an unbounded thread-per-connection model) because most of
the work here is I/O-bound (waiting on recv/send), so the GIL isn't a
bottleneck, and a bounded pool caps resource usage under load — a
flood of connections queues for a worker instead of exhausting memory
or file descriptors. (See README for how this compares to an
epoll-based event loop, and when you'd reach for one instead.)
"""

from __future__ import annotations

import logging
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from .handler import StaticFileHandler
from .request import HTTPRequest, HTTPParseError, ConnectionClosed
from .response import HTTPResponse

logger = logging.getLogger("http_server")

KEEP_ALIVE_TIMEOUT = 15   # seconds to wait for the next request on a connection
MAX_REQUESTS_PER_CONN = 100  # cap so one client can't hog a worker forever


class HTTPServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        doc_root: str = "./static",
        max_workers: int = 32,
        backlog: int = 128,
    ):
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.backlog = backlog
        self.handler = StaticFileHandler(doc_root)

        self._sock: socket.socket | None = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="conn")
        self._shutdown_event = threading.Event()

    # ----------------------------------------------------------------

    def serve_forever(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(self.backlog)
        self._sock.settimeout(1.0)  # so the accept loop can notice shutdown

        logger.info(
            "Listening on http://%s:%d (docroot=%s, workers=%d)",
            self.host, self.port, self.handler.doc_root, self.max_workers,
        )

        try:
            while not self._shutdown_event.is_set():
                try:
                    conn, addr = self._sock.accept()
                except socket.timeout:
                    continue
                self._executor.submit(self._handle_connection, conn, addr)
        finally:
            self._sock.close()

    def shutdown(self):
        logger.info("Shutting down...")
        self._shutdown_event.set()
        self._executor.shutdown(wait=True, cancel_futures=False)

    # ----------------------------------------------------------------

    def _handle_connection(self, conn: socket.socket, addr):
        conn.settimeout(KEEP_ALIVE_TIMEOUT)
        requests_served = 0
        try:
            while requests_served < MAX_REQUESTS_PER_CONN:
                try:
                    request = HTTPRequest.from_socket(conn)
                except ConnectionClosed:
                    break  # client closed cleanly between requests — not an error
                except socket.timeout:
                    break  # idle keep-alive connection past its timeout
                except HTTPParseError as e:
                    response = HTTPResponse.error(e.status, e.message)
                    conn.sendall(response.to_bytes(keep_alive=False))
                    break

                requests_served += 1
                response = self._dispatch(request)
                keep_alive = request.keep_alive and requests_served < MAX_REQUESTS_PER_CONN
                include_body = request.method != "HEAD"

                conn.sendall(response.to_bytes(keep_alive=keep_alive, include_body=include_body))
                self._log_access(addr, request, response)

                if not keep_alive:
                    break
        except (ConnectionResetError, BrokenPipeError):
            pass  # client disconnected abruptly — not a server error
        except Exception:
            logger.exception("Unhandled error serving %s", addr)
        finally:
            conn.close()

    def _dispatch(self, request: HTTPRequest) -> HTTPResponse:
        try:
            return self.handler.handle(request)
        except Exception:
            logger.exception("Handler error for %s %s", request.method, request.path)
            return HTTPResponse.error(500, "Internal server error")

    @staticmethod
    def _log_access(addr, request: HTTPRequest, response: HTTPResponse):
        logger.info(
            '%s:%d "%s %s %s" %d %s',
            addr[0], addr[1], request.method, request.path, request.version,
            response.status, response.headers.get("Content-Length", "-"),
        )
