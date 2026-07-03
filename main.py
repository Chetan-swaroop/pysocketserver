#!/usr/bin/env python3
"""
Entry point: parses CLI args, sets up logging, starts the server, and
handles Ctrl+C for a clean shutdown.

Usage:
    python3 main.py --port 8080 --docroot ./static --workers 32
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from http_server import HTTPServer


def parse_args():
    p = argparse.ArgumentParser(description="A from-scratch HTTP/1.1 server.")
    p.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    p.add_argument("--docroot", default="./static", help="Directory to serve (default: ./static)")
    p.add_argument("--workers", type=int, default=32, help="Thread pool size (default: 32)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    server = HTTPServer(
        host=args.host,
        port=args.port,
        doc_root=args.docroot,
        max_workers=args.workers,
    )

    def handle_sigint(signum, frame):
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    server.serve_forever()


if __name__ == "__main__":
    main()
