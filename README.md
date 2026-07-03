# PySocketServer

![tests](https://github.com/Chetan-swaroop/pysocketserver/actions/workflows/tests.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

A HTTP/1.1 web server implemented from scratch on raw TCP sockets — no Flask, no Django, no `http.server`. Every layer is hand-built: the socket handling, the HTTP/1.1 request parser, response framing, keep-alive connection management, and static file serving with proper caching semantics.

Built to demonstrate a working understanding of the HTTP protocol and concurrent network programming, not to hide it behind a framework.

## Features

| Feature | Detail |
|---|---|
| Raw socket server | Built on Python's `socket` module directly — no web framework |
| HTTP/1.1 keep-alive | Persistent connections with idle timeout and per-connection request cap |
| Concurrent connections | Bounded `ThreadPoolExecutor`, not thread-per-connection |
| Conditional GET | `Last-Modified` / `If-Modified-Since` → `304 Not Modified` |
| Security | Path traversal protection (blocks `..` and symlink escapes) |
| Correct HTTP semantics | `HEAD` with no body, `405 + Allow` header, `400` on malformed requests |
| MIME type detection | Automatic `Content-Type` per file extension |
| Structured logging | Apache-style access logs via Python's `logging` module |
| Graceful shutdown | Clean `SIGINT`/`SIGTERM` handling, no orphaned threads |
| Tested | Integration test suite that hits a live instance over real sockets |

## Quick start

```bash
git clone https://github.com/Chetan-swaroop/pysocketserver.git
cd pysocketserver/webserver
python main.py --port 8080 --docroot ./static
```

Visit `http://localhost:8080/`. No dependencies to install — standard library only.

**Example run** (actual output — startup log, then live access logs as requests come in):

```
2026-07-03 21:30:48 INFO Listening on 0.0.0.0:8080 (docroot=...\webserver\static, workers=32)
2026-07-03 21:30:48 INFO Open in your browser: http://localhost:8080/
2026-07-03 21:31:42 INFO 127.0.0.1:58771 "GET / HTTP/1.1" 200 525
2026-07-03 21:31:42 INFO 127.0.0.1:58771 "GET /style.css HTTP/1.1" 200 232
2026-07-03 21:31:42 INFO 127.0.0.1:58771 "GET /favicon.ico HTTP/1.1" 404 -
2026-07-03 21:31:46 INFO 127.0.0.1:58771 "GET /missing HTTP/1.1" 404 -
```

Notice all four requests reuse the same source port (`58771`) — that's HTTP/1.1 keep-alive in action: one TCP connection serving multiple requests instead of a new handshake per request.

Raw response headers, via `curl`:

```
$ curl -i http://localhost:8080/
HTTP/1.1 200 OK
Date: Fri, 03 Jul 2026 12:00:00 GMT
Server: PySocketServer/1.0
Content-Type: text/html
Content-Length: 612
Last-Modified: Fri, 03 Jul 2026 09:00:00 GMT
Cache-Control: public, max-age=60
Connection: keep-alive
```

## Running the tests

```bash
python -m unittest discover tests -v
```

9 integration tests, all exercised over real TCP connections (not mocks): static file serving, MIME types, 404s, path traversal blocking, 405 on disallowed methods, `HEAD` semantics, conditional `304` responses, keep-alive across multiple requests on one connection, and 20 concurrent requests.

## Architecture

```
main.py                    CLI entry point, argument parsing, signal handling
http_server/
  server.py                TCP accept loop, thread pool, connection lifecycle
  request.py                HTTP/1.1 request parsing straight off the socket
  response.py                 HTTP/1.1 response framing
  handler.py                    Static file serving: routing, security, caching
tests/
  test_server.py                Integration tests over real sockets
```

**Request lifecycle:** `accept()` hands a new connection to a thread pool worker → `HTTPRequest.from_socket()` reads and parses the request line, headers, and body directly from the socket (correctly handling the fact that `recv()` can return a partial request — TCP is a byte stream, not a message protocol) → `StaticFileHandler` resolves the request to a file and builds a response → the response is serialized and written back → if the connection is keep-alive, the loop waits for the next request instead of closing the socket.

## Key design decisions

- **Thread pool over thread-per-connection.** Caps resource usage under load — a burst of connections queues for a worker instead of exhausting memory or file descriptors.
- **Threads over `asyncio`/`epoll`.** The work here is I/O-bound (waiting on `recv`/`send`), so the GIL isn't a bottleneck, and threads keep the implementation readable. An event loop would scale further for tens of thousands of idle connections — see "What's next" below.
- **Defense in depth on path resolution.** `handler.py` rejects `..` path components explicitly *and* re-verifies the resolved path with `os.path.realpath` + `commonpath`, since string-checking alone doesn't catch symlink-based escapes.
- **Explicit HTTP/1.1 framing rules**, not "read once and hope": the header parser loops until it sees `\r\n\r\n`, and the body reader loops until `Content-Length` bytes have actually arrived.

## What's next (deliberately out of scope for this build)

- Event-driven I/O (`epoll`/`selectors`) to scale past thousands of concurrent idle connections
- TLS termination for HTTPS
- Chunked transfer-encoding
- Range requests (`206 Partial Content`) for resumable downloads

## License

MIT — see [LICENSE](LICENSE).
