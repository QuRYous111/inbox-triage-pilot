from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CATEGORY_PATTERNS = {
    "security": (
        r"\b(?:breach|compromised|credential|phishing|unauthorized|suspicious login)\b",
        r"\b(?:security incident|data leak)\b",
    ),
    "billing": (
        r"\b(?:invoice|payment|refund|charge|receipt|billing|overdue)\b",
        r"\b(?:paid|payable|purchase order|po number)\b",
    ),
    "support": (
        r"\b(?:bug|broken|error|failed|failure|not working|outage|downtime)\b",
        r"\b(?:support|help|cannot|can't|unable)\b",
    ),
    "sales": (
        r"\b(?:quote|pricing|demo|trial|proposal|partnership)\b",
        r"\b(?:buy|purchase|interested in|sales)\b",
    ),
}

URGENCY_PATTERNS = (
    (r"\b(?:urgent|asap|immediately|critical|emergency|overdue)\b", 35, "urgent language"),
    (r"\b(?:today|tomorrow|eod|end of day|deadline|overdue)\b", 20, "deadline language"),
    (r"\b(?:outage|downtime|breach|compromised|data leak)\b", 35, "service/security risk"),
    (r"\b(?:refund|invoice|payment|billing|charge)\b", 15, "billing issue"),
)

AMOUNT_RE = re.compile(
    r"(?:USD|EUR|GBP|RMB|CNY)\s?\d+(?:,\d{3})*(?:\.\d{1,2})?"
    r"|[$€£¥]\s?\d+(?:,\d{3})*(?:\.\d{1,2})?",
    re.IGNORECASE,
)
DEADLINE_RE = re.compile(
    r"\b(?:today|tomorrow|eod|end of day|within \d+ (?:hours?|days?)|"
    r"by (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")


@dataclass(frozen=True)
class Message:
    subject: str
    body: str
    sender: str = ""

    @classmethod
    def from_mapping(cls, value: dict) -> "Message":
        if not isinstance(value, dict):
            raise ValueError("message must be a JSON object")
        fields = {}
        for name in ("subject", "body", "sender"):
            item = value.get(name, "")
            if not isinstance(item, str):
                raise ValueError(f"{name} must be a string")
            fields[name] = item
        if not (fields["subject"].strip() or fields["body"].strip()):
            raise ValueError("subject or body is required")
        return cls(**fields)


@dataclass(frozen=True)
class TriageResult:
    category: str
    priority: str
    score: int
    reasons: list[str]
    amounts: list[str]
    deadlines: list[str]
    safe_preview: str


def _first_category(text: str) -> str:
    for category, patterns in CATEGORY_PATTERNS.items():
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            return category
    return "general"


def _redact(text: str) -> str:
    return PHONE_RE.sub("[PHONE]", EMAIL_RE.sub("[EMAIL]", text))


def triage(message: Message) -> TriageResult:
    text = " ".join(f"{message.subject} {message.body}".split())
    category = _first_category(text)

    score = 0
    reasons: list[str] = []
    for pattern, points, reason in URGENCY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            score += points
            reasons.append(reason)

    if category == "security":
        score += 25
        reasons.append("security category")
    score = min(score, 100)

    if score >= 60:
        priority = "high"
    elif score >= 25:
        priority = "medium"
    else:
        priority = "normal"

    safe_preview = _redact(text)[:240]
    return TriageResult(
        category=category,
        priority=priority,
        score=score,
        reasons=reasons,
        amounts=AMOUNT_RE.findall(text),
        deadlines=DEADLINE_RE.findall(text),
        safe_preview=safe_preview,
    )


def process_lines(lines: Iterable[str]) -> Iterable[dict]:
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            message = Message.from_mapping(raw)
            yield {"ok": True, "line": line_number, **asdict(triage(message))}
        except (json.JSONDecodeError, ValueError) as exc:
            yield {"ok": False, "line": line_number, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a structured queue from JSONL messages.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as source:
        results = list(process_lines(source))

    rendered = "\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
