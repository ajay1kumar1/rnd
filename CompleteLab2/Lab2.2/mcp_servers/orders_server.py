"""MCP server exposing order-lookup tools backed by data/orders.json."""

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "orders.json"

mcp = FastMCP("orders-server")


def _load_orders() -> list[dict[str, Any]]:
    if not DATA_FILE.is_file():
        return []
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


@mcp.tool()
def get_order(order_id: str) -> dict[str, Any]:
    """Look up a single order by its order ID.

    Args:
        order_id: The unique order identifier, e.g. "NP-100245".

    Returns:
        The matching order record, or an error message if not found.
    """
    for order in _load_orders():
        if order.get("order_id") == order_id:
            return order
    return {"error": f"No order found with order_id '{order_id}'"}


@mcp.tool()
def find_orders_by_email(email: str) -> list[dict[str, Any]]:
    """Find all orders placed by a given customer email address.

    Args:
        email: The customer's email address (case-insensitive match).

    Returns:
        A list of matching order records, empty if none are found.
    """
    email_lower = email.strip().lower()
    return [
        order
        for order in _load_orders()
        if order.get("email", "").lower() == email_lower
    ]


if __name__ == "__main__":
    mcp.run()
