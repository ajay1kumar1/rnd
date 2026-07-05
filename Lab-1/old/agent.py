"""
agent.py — Ticket-classifier agent.

Loop invariants:
  • Calls classify_ticket ONLY for fields that are still missing.
  • Stops as soon as all three required fields are confirmed.
  • Never stops before all fields are present.
  • Never loops after all fields are confirmed.
"""

from __future__ import annotations

import logging
from typing import Any

from tools import FIELD_VOCAB, REQUIRED_FIELDS, classify_ticket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Agent ───────────────────────────────────────────────────────────────────

def run_classifier_agent(ticket_text: str) -> dict[str, Any]:
    """
    Classify a ticket by iteratively calling classify_ticket until every
    required field has a confirmed value.

    Parameters
    ----------
    ticket_text : The raw support ticket text to classify.

    Returns
    -------
    A dict with keys ``product_area``, ``severity``, and ``intent``.
    """
    resolved: dict[str, Any] = {}
    iteration = 0

    log.info("── Starting ticket classification ──────────────────────────")
    log.info("Ticket : %r", ticket_text[:120])

    while True:
        iteration += 1

        # ── Determine which fields are still needed ──────────────────────
        fields_needed = [f for f in REQUIRED_FIELDS if f not in resolved]

        # ── Termination check BEFORE calling the tool ────────────────────
        if not fields_needed:
            log.info("All fields confirmed after %d iteration(s). Stopping.", iteration - 1)
            break

        log.info("Iteration %d — requesting fields: %s", iteration, fields_needed)

        # ── Call the classification tool ─────────────────────────────────
        partial_result = classify_ticket(
            ticket_text=ticket_text,
            fields_needed=fields_needed,
        )

        log.info("Tool returned: %s", partial_result)

        # ── Validate tool output ─────────────────────────────────────────
        _validate_partial(partial_result, fields_needed)

        # ── Merge into resolved state ─────────────────────────────────────
        resolved.update(partial_result)

        log.info("Resolved so far: %s", resolved)

    log.info("── Final classification ────────────────────────────────────")
    for field, value in resolved.items():
        log.info("  %-14s → %s", field, value)

    return resolved


def _validate_partial(result: dict[str, Any], expected_fields: list[str]) -> None:
    """
    Guard: ensure the tool returned exactly the fields that were requested
    and that every value is within the allowed vocabulary.

    Raises ValueError on any violation so the agent never silently accepts
    bad data and never gets stuck in an infinite loop due to stale fields.
    """
    missing = [f for f in expected_fields if f not in result]
    if missing:
        raise ValueError(
            f"classify_ticket did not return expected field(s): {missing}. "
            f"Got: {list(result.keys())}"
        )

    for field, value in result.items():
        allowed = FIELD_VOCAB.get(field, [])
        if value not in allowed:
            raise ValueError(
                f"classify_ticket returned invalid value {value!r} for field "
                f"{field!r}. Allowed: {allowed}"
            )


# ── Demo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_ticket = (
        "Hi, I was charged twice for my subscription this month. "
        "The duplicate charge is showing on my credit card statement. "
        "Please help ASAP — this is blocking our whole team."
    )

    classification = run_classifier_agent(sample_ticket)

    print("\n═══ Classification Result ═══")
    for k, v in classification.items():
        print(f"  {k:<14} = {v}")
