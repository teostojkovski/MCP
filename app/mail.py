"""
Email sending via Resend. Configure with env: RESEND_API_KEY, EMAIL_FROM.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

EMAIL_FROM = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")


def _is_valid_email(s: Optional[str]) -> bool:
    """True if s is a non-empty string containing @ (minimal validation)."""
    return bool(s and isinstance(s, str) and s.strip() and "@" in s.strip())


def send_consultation_email(
    to_email: str,
    subject: str,
    body_plain: str,
    reply_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a consultation email via Resend.
    Returns {"id": provider_message_id} on success.
    Raises ValueError if RESEND_API_KEY is missing, or to_email/reply_to invalid, or send fails.
    """
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY is not set. Set it in .env to send emails.")
    to_email = (to_email or "").strip()
    if not _is_valid_email(to_email):
        raise ValueError(
            "Cannot send: recipient (to_email) is missing or invalid. "
            "Check professors.email for the professor linked to this booking."
        )
    if reply_to is not None:
        reply_to = (reply_to or "").strip()
        if not _is_valid_email(reply_to):
            raise ValueError(
                "Cannot send: reply_to (student email) is missing or invalid. "
                "Check students.email for the student linked to this booking (table students, column email)."
            )
    import resend
    resend.api_key = RESEND_API_KEY
    from_addr = (EMAIL_FROM or "").strip()
    if not _is_valid_email(from_addr):
        raise ValueError("EMAIL_FROM is not set or invalid in .env. Use a valid sender address (e.g. onboarding@resend.dev).")
    params: Dict[str, Any] = {
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "text": body_plain,
    }
    if reply_to:
        params["reply_to"] = [reply_to]
    result = resend.Emails.send(params)
    msg_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
    if msg_id:
        return {"id": msg_id}
    raise ValueError(f"Resend did not return message id: {result}")
