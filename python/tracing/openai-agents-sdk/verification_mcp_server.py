"""Local deterministic MCP tool used by latest SDK verification."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("verification-weather")


@server.tool()
def forecast_mcp(city: str) -> str:
    """Return the verified weather for a city."""
    return f"Sunny in {city}; 22 C."


if __name__ == "__main__":
    server.run(transport="stdio")
