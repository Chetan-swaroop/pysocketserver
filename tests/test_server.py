"""
Integration tests: start a real HTTPServer on a background thread and
hit it with real TCP connections via http.client. This exercises the
actual socket/parsing/threading code paths, not mocks.

Run with:  python3 -m unittest discover tests -v
"""

from __future__ import annotations

import http.client
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from http_server import HTTPServer


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc_root = tempfile.mkdtemp()
        with open(os.path.join(cls.doc_root, "index.html"), "w") as f:
            f.write("<h1>hello</h1>")
        with open(os.path.join(cls.doc_root, "data.json"), "w") as f:
            f.write('{"ok": true}')
        os.makedirs(os.path.join(cls.doc_root, "secret"), exist_ok=True)
        with open(os.path.join(cls.doc_root, "secret", "passwords.txt"), "w") as f:
            f.write("shh")

        cls.port = free_port()
        cls.server = HTTPServer(host="127.0.0.1", port=cls.port, doc_root=cls.doc_root, max_workers=8)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls._wait_for_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        shutil.rmtree(cls.doc_root, ignore_errors=True)

    @classmethod
    def _wait_for_server(cls, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("server did not start in time")

    def conn(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)

    # ------------------------------------------------------------------

    def test_index_served_at_root(self):
        c = self.conn()
        c.request("GET", "/")
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertIn(b"hello", r.read())
        c.close()

    def test_json_mime_type(self):
        c = self.conn()
        c.request("GET", "/data.json")
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.getheader("Content-Type"), "application/json")
        c.close()

    def test_404_for_missing_file(self):
        c = self.conn()
        c.request("GET", "/nope.html")
        r = c.getresponse()
        self.assertEqual(r.status, 404)
        r.read()
        c.close()

    def test_path_traversal_blocked(self):
        c = self.conn()
        c.request("GET", "/../../../../etc/passwd")
        r = c.getresponse()
        self.assertIn(r.status, (403, 404))
        r.read()
        c.close()

    def test_method_not_allowed(self):
        c = self.conn()
        c.request("DELETE", "/")
        r = c.getresponse()
        self.assertEqual(r.status, 405)
        self.assertEqual(r.getheader("Allow"), "GET, HEAD")
        r.read()
        c.close()

    def test_head_has_no_body(self):
        c = self.conn()
        c.request("HEAD", "/")
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        body = r.read()
        self.assertEqual(body, b"")
        c.close()

    def test_conditional_get_returns_304(self):
        c = self.conn()
        c.request("GET", "/")
        r = c.getresponse()
        last_modified = r.getheader("Last-Modified")
        r.read()
        c.close()

        c = self.conn()
        c.request("GET", "/", headers={"If-Modified-Since": last_modified})
        r = c.getresponse()
        self.assertEqual(r.status, 304)
        r.read()
        c.close()

    def test_keep_alive_serves_multiple_requests_on_one_connection(self):
        c = self.conn()
        c.request("GET", "/")
        r1 = c.getresponse()
        r1.read()
        self.assertEqual(r1.status, 200)

        # Same underlying connection, second request:
        c.request("GET", "/data.json")
        r2 = c.getresponse()
        r2.read()
        self.assertEqual(r2.status, 200)
        c.close()

    def test_concurrent_requests(self):
        results = []

        def worker():
            c = self.conn()
            c.request("GET", "/")
            r = c.getresponse()
            results.append(r.status)
            r.read()
            c.close()

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(results), 20)
        self.assertTrue(all(status == 200 for status in results))


if __name__ == "__main__":
    unittest.main()
