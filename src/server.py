from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from triage import Message, triage


MAX_BODY_BYTES = 64 * 1024


class TriageHandler(BaseHTTPRequestHandler):
    server_version = "InboxTriage/1.0"

    def _send_json(self, status: int, value: dict) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/triage":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid content length"})
            return

        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "body must be between 1 and 65536 bytes"})
            return

        try:
            raw = json.loads(self.rfile.read(length))
            message = Message.from_mapping(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})
            return

        self._send_json(200, asdict(triage(message)))

    def log_message(self, format: str, *args: object) -> None:
        # Deliberately avoid default request logging; payload data may be sensitive.
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the inbox triage HTTP API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), TriageHandler)
    print(f"Listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
