"""Entity search, tagging, service level, and synthetic monitor handlers"""

from typing import Any

from mcp.types import TextContent

from .base import ToolHandlerStrategy


class EntitySearchHandler(ToolHandlerStrategy):
    """Handler for entity search"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        name = arguments.get("name")
        entity_type = arguments.get("entity_type")
        domain = arguments.get("domain")
        tags = arguments.get("tags")

        entities = await self.client.entity_search(name=name, entity_type=entity_type, domain=domain, tags=tags)

        if not entities:
            return self._create_success_response("No entities found matching the search criteria.")

        lines = [f"Found {len(entities)} entities:\n"]
        for e in entities:
            lines.append(f"- **{e.get('name', 'Unknown')}**")
            lines.append(f"  GUID: {e.get('guid', '?')}")
            lines.append(f"  Type: {e.get('domain', '?')}/{e.get('type', e.get('entityType', '?'))}")
            severity = e.get("alertSeverity")
            if severity:
                lines.append(f"  Alert severity: {severity}")
            reporting = e.get("reporting")
            if reporting is not None:
                lines.append(f"  Reporting: {reporting}")
            # Type-specific fields
            if e.get("language"):
                lines.append(f"  Language: {e['language']}")
            if e.get("monitorType"):
                lines.append(f"  Monitor type: {e['monitorType']}")
                if e.get("period"):
                    lines.append(f"  Period: {e['period']}min")
            tags_list = e.get("tags", [])
            if tags_list:
                tag_str = ", ".join([f"{t['key']}={','.join(t['values'])}" for t in tags_list[:5]])
                lines.append(f"  Tags: {tag_str}")
            lines.append("")

        return self._create_success_response("\n".join(lines))


class GetEntityTagsHandler(ToolHandlerStrategy):
    """Handler for getting entity tags"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        guid = arguments["guid"]
        entity = await self.client.get_entity_tags(guid)

        if not entity:
            return self._create_error_response(f"Entity not found for GUID: {guid}")

        tags = entity.get("tags", [])
        name = entity.get("name", "Unknown")

        if not tags:
            return self._create_success_response(f"Entity '{name}' has no tags.")

        lines = [f"Tags for '{name}' ({entity.get('entityType', '?')}):\n"]
        for tag in sorted(tags, key=lambda t: t["key"]):
            values = ", ".join(tag.get("values", []))
            lines.append(f"  {tag['key']}: {values}")

        return self._create_success_response("\n".join(lines))


class AddTagsHandler(ToolHandlerStrategy):
    """Handler for adding tags to an entity"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        guid = arguments["guid"]
        tags = arguments["tags"]

        result = await self.client.add_tags_to_entity(guid, tags)

        if "error" in result:
            return self._create_error_response(f"adding tags: {result['error']}")

        tag_str = ", ".join([f"{t['key']}={t['value']}" for t in tags])
        return self._create_success_response(f"Tags added successfully to entity {guid}: {tag_str}")


class DeleteTagsHandler(ToolHandlerStrategy):
    """Handler for deleting tags from an entity"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        guid = arguments["guid"]
        tag_keys = arguments["tag_keys"]

        result = await self.client.delete_tags_from_entity(guid, tag_keys)

        if "error" in result:
            return self._create_error_response(f"deleting tags: {result['error']}")

        return self._create_success_response(
            f"Tag keys deleted from entity {guid}: {', '.join(tag_keys)}"
        )


class ListServiceLevelsHandler(ToolHandlerStrategy):
    """Handler for listing service levels (SLOs/SLIs)"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        indicators = await self.client.list_service_levels(account_id)

        if not indicators:
            return self._create_success_response("No service level indicators found.")

        lines = [f"Found {len(indicators)} service level indicator(s):\n"]
        for sli in indicators:
            lines.append(f"- **{sli.get('name', 'Unknown')}**")
            lines.append(f"  GUID: {sli.get('guid', '?')}")
            severity = sli.get("alertSeverity")
            if severity and severity != "NOT_CONFIGURED":
                lines.append(f"  Alert severity: {severity}")
            compliance = sli.get("sliCompliance")
            if compliance is not None:
                lines.append(f"  Compliance (last 1h): {compliance}%")
            tags = sli.get("tags", [])
            sli_tags = {t["key"]: ", ".join(t["values"]) for t in tags}
            if sli_tags.get("sli.indicator"):
                lines.append(f"  Indicator: {sli_tags['sli.indicator']}")
            if sli_tags.get("nr.sli.objectiveTarget"):
                lines.append(f"  Target: {sli_tags['nr.sli.objectiveTarget']}%")
            lines.append("")

        return self._create_success_response("\n".join(lines))


class ListSyntheticMonitorsHandler(ToolHandlerStrategy):
    """Handler for listing synthetic monitors"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        monitors = await self.client.list_synthetic_monitors(account_id)

        if not monitors:
            return self._create_success_response("No synthetic monitors found.")

        lines = [f"Found {len(monitors)} synthetic monitor(s):\n"]
        for m in monitors:
            lines.append(f"- **{m.get('name', 'Unknown')}**")
            lines.append(f"  GUID: {m.get('guid', '?')}")
            lines.append(f"  Type: {m.get('monitorType', '?')}")
            period = m.get("period")
            if period:
                lines.append(f"  Period: every {period} min")
            severity = m.get("alertSeverity")
            if severity:
                lines.append(f"  Alert severity: {severity}")
            summary = m.get("monitorSummary") or {}
            if summary:
                status = summary.get("status", "?")
                success_rate = summary.get("successRate")
                failing = summary.get("locationsFailing", 0)
                running = summary.get("locationsRunning", 0)
                lines.append(f"  Status: {status}")
                if success_rate is not None:
                    lines.append(f"  Success rate: {success_rate * 100:.1f}%")
                lines.append(f"  Locations: {running - failing}/{running} passing")
            lines.append("")

        return self._create_success_response("\n".join(lines))


class GetSyntheticResultsHandler(ToolHandlerStrategy):
    """Handler for getting synthetic monitor results"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        monitor_guid = arguments["monitor_guid"]
        hours = arguments.get("hours", 24)

        data = await self.client.get_synthetic_results(account_id, monitor_guid, hours)
        entity = data.get("entity", {})
        results = data.get("results", [])

        if not entity:
            return self._create_error_response(f"Monitor not found for GUID: {monitor_guid}")

        name = entity.get("name", "Unknown")
        summary = entity.get("monitorSummary", {})

        lines = [f"Synthetic monitor: **{name}**"]
        lines.append(f"Type: {entity.get('monitorType', '?')}")
        if summary:
            lines.append(f"Status: {summary.get('status', '?')}")
            success_rate = summary.get("successRate")
            if success_rate is not None:
                lines.append(f"Success rate: {success_rate * 100:.1f}%")
            failing = summary.get("locationsFailing", 0)
            running = summary.get("locationsRunning", 0)
            lines.append(f"Locations: {running - failing}/{running} passing")
        lines.append("")

        if results:
            passed = sum(1 for r in results if r.get("result") == "SUCCESS")
            failed = len(results) - passed
            lines.append(f"Recent checks (last {hours}h): {len(results)} total, {passed} passed, {failed} failed")
            lines.append("")
            lines.append("Last 10 checks:")
            for r in results[:10]:
                status = "✅" if r.get("result") == "SUCCESS" else "❌"
                duration = r.get("duration", "?")
                location = r.get("locationLabel", "?")
                error = r.get("error", "")
                line = f"  {status} {location} ({duration}ms)"
                if error:
                    line += f" — {error}"
                lines.append(line)
        else:
            lines.append(f"No check results found in the last {hours}h.")

        return self._create_success_response("\n".join(lines))
