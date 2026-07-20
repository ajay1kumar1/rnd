# math_server.py
import sys
import logging
from mcp.server.fastmcp import FastMCP

# 1. Force the standard logging engine to print strictly to stderr.
# This prevents text logs from breaking the JSON-RPC pipe over stdout.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MathServer")

# 2. Initialize the FastMCP instance
mcp = FastMCP("MathServer")

@mcp.tool()
def add(a: float, b: float) -> float:
    """
    Adds two numbers safely together.
    
    Args:
        a: The first number.
        b: The second number.
    """
    # Safe: Log tracking goes directly to standard error
    logger.info(f"Executing tool 'add' with a={a}, b={b}")
    return a + b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """
    Multiplies two numbers safely together.
    
    Args:
        a: The first multiplier factor.
        b: The second multiplier factor.
    """
    logger.info(f"Executing tool 'multiply' with a={a}, b={b}")
    return a * b

if __name__ == "__main__":
    logger.info("Initializing Math Server via stdio transport protocol...")
    # 3. Spin up the server using stdio lines
    mcp.run(transport="stdio")
