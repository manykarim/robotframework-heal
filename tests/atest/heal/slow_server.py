"""Tiny HTTP server with an artificially slow sub-resource (timing-class atest).

Serves tests/atest/heal/pages on the given port; `/slow.png` responds after a
delay so `document.readyState` stays != 'complete' while a test interacts.
"""

import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PAGES = Path(__file__).parent / "pages"
DELAY_SECONDS = 6.0

# 1x1 transparent PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PAGES), **kwargs)

    def do_GET(self):
        if self.path.startswith("/slow.png"):
            time.sleep(DELAY_SECONDS)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG)))
            self.end_headers()
            self.wfile.write(PNG)
            return
        super().do_GET()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"slow server on :{port}", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
