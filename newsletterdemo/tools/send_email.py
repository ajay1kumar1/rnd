"""WAT tool: send_email

Single-purpose tool that "sends" a rendered email. For the demo it simply
prints to stdout unless SMTP settings are configured in the environment.

Reads configuration from environment variables — never hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SendInput:
    to: str
    subject: str
    body: str


@dataclass
class SendOutput:
    delivered: bool
    transport: str


def run(data: SendInput) -> SendOutput:
    """Send the email. This is the tool's single entry point."""
    if not data.to.strip():
        raise ValueError("recipient 'to' must not be empty")

    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        # Demo fallback: print instead of sending.
        print(f"[send_email] (stdout) To: {data.to}")
        print(f"[send_email] Subject: {data.subject}")
        print(data.body)
        return SendOutput(delivered=True, transport="stdout")

    # Real SMTP path is left as an exercise; config would come from the env.
    raise NotImplementedError("SMTP transport not implemented in this demo")
