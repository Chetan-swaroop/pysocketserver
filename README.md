# PySocketServer

A HTTP/1.1 web server built directly on top of raw TCP sockets — no
Flask, no `http.server`, no framework of any kind. Every layer (socket
handling, HTTP parsing, response framing, static file serving) is
implemented by hand, to demonstrate a real understanding of the
protocol and of concurrent network programming.

## Quick start

```bash
python3 main.py --port 8080 --docroot ./static --workers 32
```

Then visit `http://localhost:8080/`.

Run the test suite (spins up a real server and hits it over real
sockets — no mocks):

```bash
python3 -m unittest discover tests -v
```

## Architecture

```
main.py                  CLI entry point, signal handling, graceful shutdown
http_server/
  server.py               TCP accept loop + thread pool + connection lifecycle
  request.py               HTTP/1.1 request parsing (from raw socket bytes)
  response.py               HTTP/1.1 response framing
  handler.py                 Static file serving: routing, security, caching
tests/
  test_server.py               Integration tests over real sockets
```

**Request lifecycle:** `socket.accept()` → thread pool worker →
`HTTPRequest.from_socket()` parses the request line, headers, and body
directly from the socket buffer (correctly handling partial reads —
`recv()` gives no guarantee of returning a full request in one call) →
`StaticFileHandler.handle()` resolves the request to a file and builds
an `HTTPResponse` → response is serialized and written back → if
keep-alive, the loop waits for the next request on the same
connection instead of closing it.

## What it implements, and why

- **Raw sockets, not a framework.** Shows the HTTP protocol is
  understood, not just consumed through an abstraction.
- **Thread pool (`ThreadPoolExecutor`), not thread-per-connection.**
  Bounds resource usage under load — a connection flood queues for a
  worker instead of exhausting memory/file descriptors. Since the work
  is I/O-bound (waiting on `recv`/`send`), the GIL isn't a bottleneck.
- **HTTP/1.1 keep-alive.** Persistent connections with an idle timeout
  and a max-requests-per-connection cap, so one client can't hog a
  worker thread indefinitely.
- **Conditional GET (`Last-Modified` / `If-Modified-Since` → 304).**
  Real HTTP caching semantics, not just "serve the file."
- **Path traversal protection.** URL paths are normalized and checked
  against the resolved document root (defense in depth: reject `..`
  components explicitly, *and* re-verify with `os.path.realpath` to
  catch symlink escapes) before ever touching the filesystem.
- **Correct HTTP semantics for edge cases:** `HEAD` returns headers
  with no body, unsupported methods get `405` with an `Allow` header,
  malformed requests get `400`, oversized headers/bodies are rejected
  before they can be used to exhaust memory.
- **Real logging**, not print statements — structured access logs via
  Python's `logging` module.

## What a "maximal" version would add (good interview talking points)

- **Event-driven I/O (`epoll`/`selectors`)** instead of thread-per-connection,
  to scale to tens of thousands of concurrent idle connections (the
  C10K problem) — trades implementation complexity for lower memory
  overhead per connection.
- **TLS termination** via `ssl.wrap_socket` for HTTPS.
- **Chunked transfer-encoding** for responses/requests of unknown length.
- **Range requests** (`Range`/`Content-Range`, `206 Partial Content`)
  for resumable downloads and video seeking.
- **A reverse-proxy / load-balancing mode**, which is where this would
  most directly connect to Cisco-relevant networking concepts.

## Talking points for the interview

- Walk through what happens between `accept()` returning and the
  first byte of the response leaving the socket — that's the core of
  the HTTP protocol.
- Explain *why* `recv()` can return a partial request, and how the
  header-parsing loop in `request.py` handles that correctly.
- Explain the keep-alive vs. close tradeoff, and why HTTP/1.1 defaults
  to persistent connections.
- Explain the threading model's tradeoffs vs. an event loop, and when
  you'd choose one over the other at scale.
- Explain the specific security decision in `handler.py`'s
  `_resolve_path` — why checking for `..` isn't sufficient on its own
  (symlinks) and why `os.path.realpath` + `commonpath` closes that gap.
