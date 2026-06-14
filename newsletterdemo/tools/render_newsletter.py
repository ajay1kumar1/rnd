"""WAT tool: render_newsletter

Single-purpose tool that renders a newsletter into a plain-text email body
from a subject and a list of content items.

Pure function — no side effects. Inputs and outputs are typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RenderInput:
    subject: str
    items: list[str] = field(default_factory=list)
    footer: str = "You are receiving this because you subscribed."


@dataclass
class RenderOutput:
    subject: str
    body: str


def run(data: RenderInput) -> RenderOutput:
    """Render the newsletter body. This is the tool's single entry point."""
    if not data.subject.strip():
        raise ValueError("subject must not be empty")

    lines = [data.subject, "=" * len(data.subject), ""]
    for i, item in enumerate(data.items, start=1):
        lines.append(f"{i}. {item}")
    lines += ["", "---", data.footer]

    return RenderOutput(subject=data.subject, body="\n".join(lines))


if __name__ == "__main__":
    out = run(RenderInput(subject="Demo Issue #1", items=["Hello", "World"]))
    print(out.body)
