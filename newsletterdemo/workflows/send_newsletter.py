"""WAT workflow: send_newsletter

Composes WAT tools in order to render and deliver a newsletter:

    render_newsletter -> send_email

The workflow orchestrates; the tools execute. Failures fail fast with context.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

# Allow running this file directly: make the project root importable.
sys.path.insert(0, __file__.rsplit("/workflows/", 1)[0])

from tools import render_newsletter, send_email  # noqa: E402


@dataclass
class NewsletterRequest:
    to: str
    subject: str
    items: list[str]


def run(request: NewsletterRequest) -> send_email.SendOutput:
    """Run the full send-newsletter workflow."""
    try:
        rendered = render_newsletter.run(
            render_newsletter.RenderInput(subject=request.subject, items=request.items)
        )
    except Exception as exc:  # fail fast with context
        raise RuntimeError(f"render_newsletter failed: {exc}") from exc

    try:
        result = send_email.run(
            send_email.SendInput(
                to=request.to, subject=rendered.subject, body=rendered.body
            )
        )
    except Exception as exc:
        raise RuntimeError(f"send_email failed: {exc}") from exc

    print(f"[send_newsletter] delivered={result.delivered} via {result.transport}")
    return result


if __name__ == "__main__":
    run(
        NewsletterRequest(
            to="subscriber@example.com",
            subject="Demo Issue #1",
            items=[
                "Welcome to the WAT newsletter demo.",
                "This issue was rendered and sent via composed tools.",
            ],
        )
    )
