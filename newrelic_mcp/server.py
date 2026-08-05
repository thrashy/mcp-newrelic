"""
New Relic MCP Server

A Model Context Protocol server that provides tools and resources for interacting with New Relic.
Supports querying applications, metrics, incidents, dashboards, and managing alerts.
"""

import logging
from typing import Any

from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListResourcesResult,
    ListToolsResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
    TextContent,
    TextResourceContents,
)

from .client import NewRelicClient
from .config import NewRelicConfig
from .handlers import ResourceHandlers
from .handlers.tool_definitions import get_all_tools
from .handlers.tool_handlers import ToolHandlers

logger = logging.getLogger(__name__)

NOT_CONFIGURED_MESSAGE = (
    "New Relic client not configured. Provide credentials via config file, command line, or environment variables."
)


class NewRelicMCPServer:
    """New Relic MCP Server implementation"""

    def __init__(self, config: NewRelicConfig | None = None):
        self.config = config or NewRelicConfig.from_env()
        self.client: NewRelicClient | None = None

        if self.config.is_valid():
            self.client = NewRelicClient(self.config)
            logger.info("New Relic client initialized for region: %s", self.config.effective_region)
        else:
            logger.warning("New Relic credentials not provided. Server will run with limited functionality.")

        if self.client:
            self.resource_handlers = ResourceHandlers(self.client, self.config)
            self.tool_handlers = ToolHandlers(self.client, self.config)

        self.server: Server[Any] = Server(
            "newrelic-mcp",
            on_list_resources=self.handle_list_resources,
            on_read_resource=self.handle_read_resource,
            on_list_tools=self.handle_list_tools,
            on_call_tool=self.handle_call_tool,
        )

    async def handle_list_resources(
        self, _context: ServerRequestContext[Any], _params: PaginatedRequestParams | None
    ) -> ListResourcesResult:
        """List available New Relic resources"""
        if not self.client:
            return ListResourcesResult(resources=[])
        return ListResourcesResult(resources=self.resource_handlers.get_resources())

    async def handle_read_resource(
        self, _context: ServerRequestContext[Any], params: ReadResourceRequestParams
    ) -> ReadResourceResult:
        """Read a specific New Relic resource"""
        if not self.client:
            raise ValueError(NOT_CONFIGURED_MESSAGE)
        uri = str(params.uri)
        text = await self.resource_handlers.read_resource(uri)
        return ReadResourceResult(
            contents=[TextResourceContents(uri=uri, mime_type="application/json", text=text)],
        )

    async def handle_list_tools(
        self, _context: ServerRequestContext[Any], _params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        """List available New Relic tools"""
        return ListToolsResult(tools=get_all_tools())

    async def handle_call_tool(
        self, _context: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        """Handle tool calls"""
        if not self.client:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {NOT_CONFIGURED_MESSAGE}")],
                is_error=True,
            )
        content = await self.tool_handlers.handle_tool_call(params.name, params.arguments or {})
        return CallToolResult(content=list(content))

    async def run(self) -> None:
        """Run the MCP server"""
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(read_stream, write_stream, self.server.create_initialization_options())
        finally:
            if self.client:
                await self.client.aclose()
