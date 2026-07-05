"""
tools.py — Ticket classification tool for the agentic loop.

In production, classify_ticket would call a real ML model or rules engine.
For this lab, values are simulated (randomly selected from the field vocabulary).
"""

import random
from typing import Any

# ── Field vocabulary ────────────────────────────────────────────────────────
FIELD_VOCAB: dict[str, list[str]] = {
    "product_area": ["Billing", "Platform", "Integrations", "Security", "Onboarding"],
    "severity":     ["P1-Critical", "P2-High", "P3-Medium", "P4-Low"],
    "intent":       ["Bug", "Question", "Feature Request", "Billing Dispute"],
}

REQUIRED_FIELDS: list[str] = list(FIELD_VOCAB.keys())   # ["product_area", "severity", "intent"]


def classify_ticket(ticket_text: str, fields_needed: list[str]) -> dict[str, Any]:
    """
    Classify a support ticket and return only the requested fields.

    Parameters
    ----------
    ticket_text   : The raw text of the support ticket.
    fields_needed : A subset of REQUIRED_FIELDS to resolve in this call.

    Returns
    -------
    A dict whose keys are exactly the elements of ``fields_needed`` and whose
    values are drawn from the corresponding FIELD_VOCAB lists.

    Raises
    ------
    ValueError  – if an unknown field name is requested.
    """
    if not ticket_text or not ticket_text.strip():
        raise ValueError("ticket_text must be a non-empty string.")

    unknown = [f for f in fields_needed if f not in FIELD_VOCAB]
    if unknown:
        raise ValueError(
            f"Unknown field(s) requested: {unknown}. "
            f"Valid fields are: {REQUIRED_FIELDS}"
        )

    # Simulate classification — in production replace this with model/rules calls.
    result: dict[str, Any] = {
        field: random.choice(FIELD_VOCAB[field])
        for field in fields_needed
    }

    return result
