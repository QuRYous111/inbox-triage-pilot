# Inbox Triage Pilot

A small, dependency-free automation that turns raw inbound messages into a
structured work queue. It is designed as a transparent pilot for email, support,
and back-office automation projects.

## What it does

- classifies messages into billing, support, sales, security, or general;
- assigns a priority score with human-readable reasons;
- extracts monetary amounts and deadline phrases;
- masks email addresses and phone numbers before logs leave the workflow;
- exposes a tiny HTTP API that can be called from n8n, Make, Zapier, or a custom
  integration;
- includes deterministic tests and sample data.

No API key or third-party service is required. The rules are intentionally
simple and auditable; an LLM can be added later behind the same response schema
when a use case justifies the extra cost and privacy trade-off.

## Quick start

Requires Python 3.11+.

```bash
python -m unittest discover -s tests -v
python src/triage.py sample/inbox.jsonl --output work-queue.jsonl
python src/server.py --port 8787
```

Example API request:

```bash
curl -X POST http://localhost:8787/triage \
  -H "Content-Type: application/json" \
  -d "{\"subject\":\"Invoice overdue\",\"body\":\"Please pay USD 120 by tomorrow\",\"sender\":\"accounts@example.com\"}"
```

Example response:

```json
{
  "category": "billing",
  "priority": "high",
  "score": 70,
  "reasons": ["deadline language", "billing issue"],
  "amounts": ["USD 120"],
  "deadlines": ["tomorrow"],
  "safe_preview": "Invoice overdue Please pay USD 120 by tomorrow"
}
```

## Integration shape

```text
Email/Webhook -> POST /triage -> Router
                              -> urgent Slack/Teams alert
                              -> billing queue
                              -> CRM/support ticket
                              -> audit log
```

The API rejects oversized requests, validates field types, returns stable JSON,
and avoids logging raw sender details. Those constraints are deliberate: small
automations still need predictable failure modes and privacy boundaries.

## Files

- `src/triage.py` — classification engine and JSONL CLI
- `src/server.py` — standard-library HTTP service
- `tests/test_triage.py` — behavior and API tests
- `sample/inbox.jsonl` — synthetic sample messages

## Scope for a paid pilot

For a real client, the next step would be to replace the sample input with one
inbox or webhook, map categories to the client's actual queues, add idempotency,
and document deployment and handoff. Credentials and production data should be
provided only after scope and payment terms are agreed.
