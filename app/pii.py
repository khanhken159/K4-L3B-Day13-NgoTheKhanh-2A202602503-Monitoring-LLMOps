from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "passport": (
        r"(?i)\b(?:passport|hộ\s*chiếu|so\s*ho\s*chieu)\s*"
        r"(?:number|no\.?|số)?\s*[:#-]?\s*[A-Z]\d{7}\b"
    ),
    # Redact the value following an explicit address label through the end of
    # its clause/line. The label is intentionally part of the matched value.
    "address": r"(?i)\b(?:địa\s*chỉ|dia\s*chi|address)\s*[:：]?\s*[^;\n]+",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
