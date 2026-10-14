"""Live round trip of every dashboard tool against a real account.

Creates a PRIVATE scratch dashboard, drives each tool through ToolHandlers (so write and
destructive gating are exercised too), reads the result back from NerdGraph, and deletes
the dashboard at the end. The snapshot step only runs on a markdown-only page, because a
snapshot URL is public.

Run with:  RUN_LIVE_TESTS=1 NEW_RELIC_API_KEY=... NEW_RELIC_ACCOUNT_ID=... uv run pytest tests/test_live_dashboards.py
"""

import asyncio
import json
import os
import re
import time

import pytest

from newrelic_mcp.client.unified_client import NewRelicClient
from newrelic_mcp.config import NewRelicConfig
from newrelic_mcp.handlers.tool_handlers import ToolHandlers
from newrelic_mcp.types import ApiError

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS") or not os.getenv("NEW_RELIC_API_KEY"),
    reason="live tests need RUN_LIVE_TESTS=1 and New Relic credentials",
)

TIMESERIES = "SELECT count(*) FROM Transaction SINCE 1 day ago TIMESERIES 1 hour"


@pytest.fixture
def setup():
    config = NewRelicConfig.from_env()
    config.enable_writes = True
    config.enable_destructive = True
    client = NewRelicClient(config)
    return ToolHandlers(client, config), client


async def call(handlers: ToolHandlers, tool: str, /, **arguments) -> str:
    result = await handlers.handle_tool_call(tool, arguments)
    text = result.content[0].text
    assert not result.is_error, f"{tool} failed: {text}"
    return text


async def widget_by_title(client: NewRelicClient, dashboard_guid: str, title: str) -> tuple[str, dict]:
    exported = await client.dashboards.export_dashboard(dashboard_guid)
    assert not isinstance(exported, ApiError), exported
    for page in exported["pages"]:
        for widget in page["widgets"]:
            if widget["title"] == title:
                return page["guid"], widget
    raise AssertionError(f"no widget titled {title!r}")


async def test_dashboard_tools_round_trip(setup):
    handlers, client = setup
    text = await call(
        handlers,
        "create_dashboard",
        name=f"zz mcp-newrelic live test {int(time.time())} (safe to delete)",
        permissions="PRIVATE",
    )
    dashboard_guid = re.search(r"GUID: (\S+)", text).group(1)
    try:
        await call(
            handlers,
            "add_widget_to_dashboard",
            dashboard_guid=dashboard_guid,
            widget_title="Notes",
            widget_type="markdown",
            text="# How it works",
            link_url="https://example.com/runbook",
            layout={"column": 1, "row": 1, "width": 4, "height": 3},
        )
        await call(
            handlers,
            "add_widget_to_dashboard",
            dashboard_guid=dashboard_guid,
            widget_title="Per hour",
            widget_type="stacked-bar",
            widget_query=TIMESERIES,
            layout={"column": 5, "row": 1, "width": 8, "height": 3},
        )
        await call(
            handlers,
            "add_widget_to_dashboard",
            dashboard_guid=dashboard_guid,
            widget_title="Count",
            widget_type="billboard",
            widget_query="SELECT count(*) FROM Transaction SINCE 1 hour ago",
            raw_configuration={"thresholds": [{"alertSeverity": "WARNING", "value": 1}]},
        )

        text = await call(handlers, "add_dashboard_page", dashboard_guid=dashboard_guid, name="Second")
        second_page = re.search(r"Page GUID: (\S+)", text).group(1)
        await call(
            handlers,
            "add_widget_to_dashboard",
            dashboard_guid=dashboard_guid,
            page_guid=second_page,
            widget_title="Second page line",
            widget_query=TIMESERIES,
        )
        page_guid, line = await widget_by_title(client, dashboard_guid, "Second page line")
        assert page_guid == second_page
        assert line["visualization"] == {"id": "viz.line"}

        listing = await call(handlers, "get_dashboard_widgets", dashboard_guid=dashboard_guid)
        assert "Permissions: PRIVATE" in listing
        assert "Layout: column 5, row 1, width 8, height 3" in listing
        assert "Link: https://example.com/runbook" in listing
        assert TIMESERIES in listing

        page_guid, stacked = await widget_by_title(client, dashboard_guid, "Per hour")
        await call(handlers, "update_widget", page_guid=page_guid, widget_id=stacked["id"], widget_title="Per hour v2")
        _, after = await widget_by_title(client, dashboard_guid, "Per hour v2")
        assert after["visualization"] == {"id": "viz.stacked-bar"}
        assert after["layout"] == stacked["layout"]
        assert after["rawConfiguration"] == stacked["rawConfiguration"]

        new_query = "SELECT average(duration) FROM Transaction SINCE 1 day ago TIMESERIES 1 hour"
        await call(handlers, "update_widget", page_guid=second_page, widget_id=line["id"], widget_query=new_query)
        _, line_after = await widget_by_title(client, dashboard_guid, "Second page line")
        assert line_after["visualization"] == {"id": "viz.line"}
        assert line_after["rawConfiguration"]["nrqlQueries"][0]["query"] == new_query

        page_guid, notes = await widget_by_title(client, dashboard_guid, "Notes")
        await call(handlers, "update_widget", page_guid=page_guid, widget_id=notes["id"], text="# Updated")
        _, notes_after = await widget_by_title(client, dashboard_guid, "Notes")
        assert notes_after["rawConfiguration"]["text"] == "# Updated"
        assert notes_after["link"] == {"url": "https://example.com/runbook"}
        assert notes_after["layout"] == notes["layout"]

        variables = [
            {
                "name": "env",
                "title": "Environment",
                "type": "ENUM",
                "replacementStrategy": "STRING",
                "items": [{"title": "a", "value": "a"}, {"title": "b", "value": "b"}],
                "defaultValues": [{"value": {"string": "a"}}],
            }
        ]
        await call(
            handlers, "update_dashboard", guid=dashboard_guid, variables=variables, permissions="PUBLIC_READ_ONLY"
        )
        await call(handlers, "update_dashboard", guid=dashboard_guid, description="renamed keeps variables")
        exported = json.loads(await call(handlers, "export_dashboard", dashboard_guid=dashboard_guid))
        assert exported["permissions"] == "PUBLIC_READ_ONLY"
        assert exported["description"] == "renamed keeps variables"
        assert [v["name"] for v in exported["variables"]] == ["env"]
        assert sum(len(p["widgets"]) for p in exported["pages"]) == 4

        exported["pages"][1]["widgets"][0]["title"] = "Replaced title"
        await call(handlers, "replace_dashboard", dashboard_guid=dashboard_guid, dashboard=exported)
        _, replaced = await widget_by_title(client, dashboard_guid, "Replaced title")
        assert replaced["id"] == line["id"]

        text = await call(handlers, "add_dashboard_page", dashboard_guid=dashboard_guid, name="Snapshot")
        snapshot_page = re.search(r"Page GUID: (\S+)", text).group(1)
        await call(
            handlers,
            "add_widget_to_dashboard",
            dashboard_guid=dashboard_guid,
            page_guid=snapshot_page,
            widget_title="Snapshot text",
            widget_type="markdown",
            text="mcp-newrelic live test snapshot (text only)",
        )
        text = await call(handlers, "create_dashboard_snapshot_url", page_guid=snapshot_page, format="PNG")
        assert re.search(r"https://\S+", text)

        await call(handlers, "delete_dashboard", dashboard_guid=dashboard_guid)
        await call(handlers, "undelete_dashboard", dashboard_guid=dashboard_guid)
        restored = await client.dashboards.export_dashboard(dashboard_guid)
        assert not isinstance(restored, ApiError), restored
    finally:
        await delete_with_retry(handlers, dashboard_guid)


async def delete_with_retry(handlers: ToolHandlers, dashboard_guid: str) -> None:
    """A delete straight after an undelete can fail while the restore propagates."""
    for _ in range(4):
        result = await handlers.handle_tool_call("delete_dashboard", {"dashboard_guid": dashboard_guid})
        if not result.is_error:
            return
        await asyncio.sleep(10)
    raise AssertionError(f"scratch dashboard {dashboard_guid} was not deleted: {result.content[0].text}")
