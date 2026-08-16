# client.py
import asyncio
import sys
import os
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_math_client():
    # 1. Configure the server parameters to map to your python environment
    server_parameters = StdioServerParameters(
        command=sys.executable,  # Uses the exact same Python binary
        args=["mathserver.py"], # Targets our server file
        env=os.environ.copy()    # Inherits your system terminal environment paths
    )
    
    # 2. Use an AsyncExitStack to handle cross-process lifecycle cleaning
    async with AsyncExitStack() as stack:
        print("[Client] Starting background mathserver.py process...")
        
        # Connect to the server process standard input/output streams
        read_stream, write_stream = await stack.enter_async_context(
            stdio_client(server_parameters)
        )
        
        # Open up the operational client session mapper
        session = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        
        # 3. Trigger the initial handshake sequence
        print("[Client] Performing capability handshake protocol...")
        await session.initialize()
        print("[Client] Connection established and valid.")

        # 4. Programmatically inspect what functions the server offers
        available_tools = await session.list_tools()
        print("\n[Client] Discovered available server tools:")
        for tool in available_tools.tools:
            print(f" - Tool Name: '{tool.name}'")
            print(f"   Description: {tool.description}")

        # 5. Call the multiply tool with parameters
        print("\n[Client] Requesting remote execution: multiply(a=12.5, b=4.0)")
        result = await session.call_tool(
            name="multiply",
            arguments={"a": 12.5, "b": 4.0}
        )
        
        # 6. Extract textual responses from content payloads
        print("\n[Server Response Received Successfully]")
        for block in result.content:
            if hasattr(block, 'text'):
                print(f"Result Output: {block.text}")

if __name__ == "__main__":
    # Start the event loop framework
    try:
        asyncio.run(run_math_client())
    except Exception as e:
        print(f"\n[Client Error Hook] Process died: {e}", file=sys.stderr)
