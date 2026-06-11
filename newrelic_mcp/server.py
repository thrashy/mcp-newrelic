"""
New Relic MCP Server

A Model Context Protocol server that provides tools and resources for interacting with New Relic.
Supports querying applications, metrics, incidents, dashboards, and managing alerts.
"""

import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from .client import NewRelicClient
from .config import NewRelicConfig
from .handlers import ResourceHandlers
from .handlers.tool_definitions import get_all_tools
from .handlers.tool_handlers import ToolHandlers

logger = logging.getLogger(__name__)


class NewRelicMCPServer:
    """New Relic MCP Server implementation"""

    def __init__(self, config: NewRelicConfig | None = None):
        self.server = Server("newrelic-mcp")
        self.config = config or NewRelicConfig.from_env()
        self.client: NewRelicClient | None = None

        if self.config.is_valid():
            self.client = NewRelicClient(self.config)
            logger.info("New Relic client initialized for region: %s", self.config.effective_region)
        else:
            logger.warning("New Relic credentials not provided. Server will run with limited functionality.")

        # Initialize handlers
        if self.client:
            self.resource_handlers = ResourceHandlers(self.client, self.config)
            self.tool_handlers = ToolHandlers(self.client, self.config)

        self.setup_handlers()

    def setup_handlers(self) -> None:
        """Setup MCP server handlers"""

        @self.server.list_resources()
        async def handle_list_resources() -> list:
            """List available New Relic resources"""
            if not self.client:
                return []
            return self.resource_handlers.get_resources()

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific New Relic resource"""
            if not self.client:
                raise ValueError(
                    "New Relic client not configured. Provide credentials via config file, command line, or environment variables."
                )
            return await self.resource_handlers.read_resource(uri)

        @self.server.list_tools()
        async def handle_list_tools() -> list:
            """List available New Relic tools"""
            return get_all_tools()

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list:
            """Handle tool calls"""
            if not self.client:
                return [
                    TextContent(
                        type="text",
                        text="Error: New Relic client not configured. Provide credentials via config file, command line, or environment variables.",
                    )
                ]

            return await self.tool_handlers.handle_tool_call(name, arguments)

    async def run(self) -> None:
        """Run the MCP server"""
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(read_stream, write_stream, self.server.create_initialization_options())
        finally:
            if self.client:
                await self.client.aclose()
