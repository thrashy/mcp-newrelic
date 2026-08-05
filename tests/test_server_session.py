"""End-to-end tests that drive NewRelicMCPServer over a real MCP session."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from newrelic_mcp.config import NewRelicConfig
from newrelic_mcp.server import NewRelicMCPServer


@asynccontextmanager
async def connected_session(server: NewRelicMCPServer) -> AsyncIterator[ClientSession]:
    async with create_client_server_memory_streams() as ((client_read, client_write), (server_read, server_write)):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                lambda: server.server.run(server_read, server_write, server.server.create_initialization_options())
            )
            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                yield session
            task_group.cancel_scope.cancel()


@pytest.fixture
def server(config: NewRelicConfig) -> NewRelicMCPServer:
    return NewRelicMCPServer(config)


class TestServerSession:
    async def test_initialize_reports_server_name(self, server):
        async with connected_session(server) as session:
            result = await session.initialize()
            assert result.server_info.name == "newrelic-mcp"

    async def test_list_tools_exposes_every_tool_with_a_schema(self, server):
        async with connected_session(server) as session:
            tools = (await session.list_tools()).tools
            assert len(tools) == 52
            assert all(tool.input_schema.get("type") == "object" for tool in tools)

    async def test_list_resources_over_the_wire(self, server):
        async with connected_session(server) as session:
            uris = [str(r.uri) for r in (await session.list_resources()).resources]
            assert "newrelic://applications" in uris


class TestUnconfiguredServer:
    async def test_call_tool_reports_missing_credentials(self):
        async with connected_session(NewRelicMCPServer(NewRelicConfig())) as session:
            result = await session.call_tool("query_nrql", {"nrql": "SELECT 1"})
            assert result.is_error
            assert "not configured" in result.content[0].text

    async def test_list_resources_is_empty(self):
        async with connected_session(NewRelicMCPServer(NewRelicConfig())) as session:
            assert (await session.list_resources()).resources == []
