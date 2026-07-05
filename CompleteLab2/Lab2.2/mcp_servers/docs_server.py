"""MCP server exposing documentation lookup tools backed by data/docs/*.md."""

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"

mcp = FastMCP("docs-server")


def _doc_paths() -> list[Path]:
    if not DATA_DIR.is_dir():
        return []
    return sorted(DATA_DIR.glob("*.md"))


def _title_for(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem


def _resolve_doc_path(name: str) -> Path | None:
    candidate = name if name.endswith(".md") else f"{name}.md"
    for path in _doc_paths():
        if path.name == candidate or path.stem == name:
            return path
    return None


@mcp.tool()
def list_docs() -> list[dict[str, str]]:
    """List all available documents.

    Returns:
        A list of {"name": ..., "title": ...} entries, one per document.
        Use the "name" value with read_doc().
    """
    return [
        {"name": path.stem, "title": _title_for(path)}
        for path in _doc_paths()
    ]


@mcp.tool()
def read_doc(name: str) -> dict[str, Any]:
    """Read the full contents of a document by name.

    Args:
        name: The document name as returned by list_docs() (with or
            without the .md extension).

    Returns:
        {"name", "title", "content"} on success, or an "error" message
        if no matching document exists.
    """
    path = _resolve_doc_path(name)
    if path is None:
        return {"error": f"No document found with name '{name}'"}
    return {
        "name": path.stem,
        "title": _title_for(path),
        "content": path.read_text(encoding="utf-8"),
    }


@mcp.tool()
def search_docs(query: str) -> list[dict[str, Any]]:
    """Search all documents for a case-insensitive text match.

    Args:
        query: The text to search for.

    Returns:
        A list of {"name", "title", "snippets"} for each document that
        contains at least one match, where "snippets" is the list of
        matching lines (stripped of leading/trailing whitespace).
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return []

    results = []
    for path in _doc_paths():
        lines = path.read_text(encoding="utf-8").splitlines()
        snippets = [line.strip() for line in lines if query_lower in line.lower()]
        if snippets:
            results.append(
                {
                    "name": path.stem,
                    "title": _title_for(path),
                    "snippets": snippets,
                }
            )
    return results


if __name__ == "__main__":
    mcp.run()
