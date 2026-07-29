from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from server import TriageHandler  # noqa: E402
from triage import Message, process_lines, triage  # noqa: E402


class TriageTests(unittest.TestCase):
    def test_billing_deadline_is_high_priority(self) -> None:
        result = triage(
            Message(
                subject="Invoice overdue",
                body="Please pay USD 120 by tomorrow.",
                sender="accounts@example.com",
            )
        )
        self.assertEqual(result.category, "billing")
        self.assertEqual(result.priority, "high")
        self.assertEqual(result.amounts, ["USD 120"])
        self.assertEqual(result.deadlines, ["tomorrow"])

    def test_security_always_receives_extra_weight(self) -> None:
        result = triage(Message(subject="Suspicious login", body="Credential compromised"))
        self.assertEqual(result.category, "security")
        self.assertEqual(result.priority, "high")
        self.assertIn("security category", result.reasons)

    def test_preview_redacts_contact_details(self) -> None:
        result = triage(
            Message(
                subject="Call me",
                body="Use person@example.com or +1 (212) 555-0198.",
            )
        )
        self.assertNotIn("person@example.com", result.safe_preview)
        self.assertNotIn("555-0198", result.safe_preview)
        self.assertIn("[EMAIL]", result.safe_preview)
        self.assertIn("[PHONE]", result.safe_preview)

    def test_bad_jsonl_record_does_not_stop_batch(self) -> None:
        records = list(
            process_lines(
                [
                    '{"subject":"Demo request","body":"Send pricing"}\n',
                    "{bad json}\n",
                    '{"subject":"Bug","body":"Login failed"}\n',
                ]
            )
        )
        self.assertEqual([item["ok"] for item in records], [True, False, True])
        self.assertEqual(records[1]["line"], 2)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), TriageHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_health(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/health") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response), {"status": "ok"})

    def test_triage_endpoint(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/triage",
            data=json.dumps({"subject": "Need a demo", "body": "Send a quote"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            body = json.load(response)
        self.assertEqual(body["category"], "sales")

    def test_invalid_request_returns_400(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/triage",
            data=b'{"subject": 42}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
