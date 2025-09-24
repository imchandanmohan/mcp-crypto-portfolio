# src/server.py
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from fastmcp import FastMCP   # <-- correct import

load_dotenv()

mcp = FastMCP("mcp-crypto-portfolio")

class HealthOut(BaseModel):
    ok: bool
    version: str

@mcp.tool
def health() -> HealthOut:
    """Basic health check for the server."""
    return HealthOut(ok=True, version="0.1.0")

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "3333"))
    print(f"[mcp] HTTP at http://{host}:{port}/mcp")
    mcp.run(transport="http", host=host, port=port)  # valid with FastMCP
