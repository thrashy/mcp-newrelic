"""Entity search, tagging, service level, and synthetic monitor handlers"""

from typing import Any

from mcp.types import TextContent

from ...validators import InputValidator
from .base import ToolHandlerStrategy


class EntitySearchHandler(ToolHandlerStrategy):
    """Handler for entity search"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        name = arguments.get("name")
        entity_type = arguments.get("entity_type")
        domain = arguments.get("domain")
        tags = arguments.get("tags")
        limit = arguments.get("limit", 25)
        minimal_output = arguments.get("minimal_output", False)

        result = await self.client.entities.entity_search(
            name=name, entity_type=entity_type, domain=domain, tags=tags,
            limit=limit, minimal_output=minimal_output,
        )

        format_fn = self._format_entity_minimal if minimal_output else self._format_entity
        return self._handle_list_response(
            result,
            error_context="searching entities",
            empty_message="No entities found matching the search criteria.",
            item_noun="entities",
            format_item=format_fn,
        )

    @staticmethod
    def _entity_header(e: dict[str, Any]) -> list[str]:
        """Common entity header fields shared by minimal and full formatters."""
        parts = [
            f"- **{e.get('name', 'Unknown')}**",
            f"  GUID: {e.get('guid', '?')}",
            f"  Type: {e.get('domain', '?')}/{e.get('type', e.get('entityType', '?'))}",
        ]
        severity = e.get("alertSeverity")
        if severity:
            parts.append(f"  Alert severity: {severity}")
        return parts

    @classmethod
    def _format_entity_minimal(cls, e: dict[str, Any]) -> str:
        return "\n".join(cls._entity_header(e)) + "\n\n"

    @classmethod
    def _format_entity(cls, e: dict[str, Any]) -> str:
        parts = cls._entity_header(e)
        reporting = e.get("reporting")
        if reporting is not None:
            parts.append(f"  Reporting: {reporting}")
        if e.get("language"):
            parts.append(f"  Language: {e['language']}")
        if e.get("monitorType"):
            parts.append(f"  Monitor type: {e['monitorType']}")
            if e.get("period"):
                parts.append(f"  Period: {e['period']}min")
        tags_list = e.get("tags", [])
        if tags_list:
            tag_str = ", ".join(f"{t['key']}={','.join(t['values'])}" for t in tags_list[:5])
            if len(tags_list) > 5:
                tag_str += f" ... (+{len(tags_list) - 5} more)"
            parts.append(f"  Tags: {tag_str}")
        return "\n".join(parts) + "\n\n"


class DecodeEntityGuidHandler(ToolHandlerStrategy):
    """Handler for decoding entity GUIDs"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        guid = arguments["guid"]
        try:
            decoded = self.client.base.decode_entity_guid(guid)
        except ValueError as e:
            return self._create_error_response(str(e))

        return self._create_success_response(
            f"Decoded entity GUID:\n"
            f"  Account ID: {decoded.account_id}\n"
            f"  Domain: {decoded.domain}\n"
            f"  Entity Type: {decoded.entity_type}\n"
            f"  Domain ID: {decoded.domain_id}"
        )


class GetEntityHandler(ToolHandlerStrategy):
    """Handler for looking up a single entity by GUID"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        guid = self._require_guid(arguments)

        entity = self._unwrap(
            await self.client.base.get_entity(guid),
            f"looking up entity {guid}",
        )

        return self._create_success_response(self._format_entity_detail(entity))

    @staticmethod
    def _format_entity_detail(e: dict[str, Any]) -> str:
        parts = [
            f"Entity: **{e.get('name', 'Unknown')}**",
            f"  GUID: {e.get('guid', '?')}",
            f"  Type: {e.get('domain', '?')}/{e.get('type', e.get('entityType', '?'))}",
        ]
        account = e.get("account")
        if account:
            parts.append(f"  Account: {account.get('name', '?')} (ID: {account.get('id', '?')})")
        severity = e.get("alertSeverity")
        if severity:
            parts.append(f"  Alert severity: {severity}")
        reporting = e.get("reporting")
        if reporting is not None:
            parts.append(f"  Reporting: {reporting}")
        permalink = e.get("permalink")
        if permalink:
            parts.append(f"  Permalink: {permalink}")
        if e.get("language"):
            parts.append(f"  Language: {e['language']}")
        if e.get("applicationId"):
            parts.append(f"  Application ID: {e['applicationId']}")
        versions = e.get("runningAgentVersions")
        if versions:
            parts.append(f"  Agent versions: {versions.get('minVersion', '?')} - {versions.get('maxVersion', '?')}")
        if e.get("monitorType"):
            parts.append(f"  Monitor type: {e['monitorType']}")
            if e.get("period"):
                parts.append(f"  Period: {e['period']}min")
        host_summary = e.get("hostSummary")
        if host_summary:
            cpu = host_summary.get("cpuUtilizationPercent")
            mem = host_summary.get("memoryUsedPercent")
            if cpu is not None:
                parts.append(f"  CPU: {cpu:.1f}%")
            if mem is not None:
                parts.append(f"  Memory: {mem:.1f}%")
        tags_list = e.get("tags", [])
        if tags_list:
            parts.append(f"  Tags ({len(tags_list)}):")
            for t in sorted(tags_list, key=lambda x: x["key"]):
                parts.append(f"    {t['key']}: {', '.join(t.get('values', []))}")
        return "\n".join(parts)


class GetEntityTagsHandler(ToolHandlerStrategy):
    """Handler for getting entity tags"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        guid = self._require_guid(arguments)

        entity = self._unwrap(
            await self.client.entities.get_entity_tags(guid),
            f"getting tags for {guid}",
        )

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

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        guid = self._require_guid(arguments)
        tags = arguments["tags"]

        self._unwrap(
            await self.client.entities.add_tags_to_entity(guid, tags),
            "adding tags",
        )

        return self._create_success_response(f"Tags added successfully to entity {guid}: {self._format_tag_str(tags)}")


class DeleteTagsHandler(ToolHandlerStrategy):
    """Handler for deleting tags from an entity"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        guid = self._require_guid(arguments)
        tag_keys = arguments["tag_keys"]

        self._unwrap(
            await self.client.entities.delete_tags_from_entity(guid, tag_keys),
            "deleting tags",
        )

        return self._create_success_response(
            f"Tag keys deleted from entity {guid}: {', '.join(tag_keys)}"
        )


class ReplaceTagsHandler(ToolHandlerStrategy):
    """Handler for replacing all tags on an entity"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        guid = self._require_guid(arguments)
        tags = arguments["tags"]

        self._unwrap(
            await self.client.entities.replace_tags_on_entity(guid, tags),
            "replacing tags",
        )

        return self._create_success_response(
            f"All tags replaced on entity {guid}: {self._format_tag_str(tags)}"
        )


class DeleteTagValuesHandler(ToolHandlerStrategy):
    """Handler for deleting specific tag values from an entity"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        guid = self._require_guid(arguments)
        tag_values = arguments["tag_values"]

        self._unwrap(
            await self.client.entities.delete_tag_values(guid, tag_values),
            "deleting tag values",
        )

        return self._create_success_response(
            f"Tag values deleted from entity {guid}: {self._format_tag_str(tag_values)}"
        )


class ListServiceLevelsHandler(ToolHandlerStrategy):
    """Handler for listing service levels (SLOs/SLIs)"""

    async def handle(self, _arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        result = await self.client.entities.list_service_levels(account_id)
        return self._handle_list_response(
            result,
            error_context="listing service levels",
            empty_message="No service level indicators found.",
            item_noun="service level indicator(s)",
            format_item=self._format_sli,
        )

    @staticmethod
    def _format_sli(sli: dict[str, Any]) -> str:
        parts = [f"- **{sli.get('name', 'Unknown')}**", f"  GUID: {sli.get('guid', '?')}"]
        severity = sli.get("alertSeverity")
        if severity and severity != "NOT_CONFIGURED":
            parts.append(f"  Alert severity: {severity}")
        compliance = sli.get("sliCompliance")
        if compliance is not None:
            parts.append(f"  Compliance (last 1h): {compliance}%")
        tags = sli.get("tags", [])
        sli_tags = {t["key"]: ", ".join(t["values"]) for t in tags}
        if sli_tags.get("sli.indicator"):
            parts.append(f"  Indicator: {sli_tags['sli.indicator']}")
        if sli_tags.get("nr.sli.objectiveTarget"):
            parts.append(f"  Target: {sli_tags['nr.sli.objectiveTarget']}%")
        return "\n".join(parts) + "\n\n"


class ListSyntheticMonitorsHandler(ToolHandlerStrategy):
    """Handler for listing synthetic monitors"""

    async def handle(self, _arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        result = await self.client.entities.list_synthetic_monitors(account_id)
        return self._handle_list_response(
            result,
            error_context="listing synthetic monitors",
            empty_message="No synthetic monitors found.",
            item_noun="synthetic monitor(s)",
            format_item=self._format_monitor,
        )

    @staticmethod
    def _format_monitor(m: dict[str, Any]) -> str:
        parts = [
            f"- **{m.get('name', 'Unknown')}**",
            f"  GUID: {m.get('guid', '?')}",
            f"  Type: {m.get('monitorType', '?')}",
        ]
        period = m.get("period")
        if period:
            parts.append(f"  Period: every {period} min")
        severity = m.get("alertSeverity")
        if severity:
            parts.append(f"  Alert severity: {severity}")
        summary = m.get("monitorSummary") or {}
        if summary:
            status = summary.get("status", "?")
            success_rate = summary.get("successRate")
            failing = summary.get("locationsFailing", 0)
            running = summary.get("locationsRunning", 0)
            parts.append(f"  Status: {status}")
            if success_rate is not None:
                parts.append(f"  Success rate: {success_rate * 100:.1f}%")
            parts.append(f"  Locations: {running - failing}/{running} passing")
        return "\n".join(parts) + "\n\n"


class GetSyntheticResultsHandler(ToolHandlerStrategy):
    """Handler for getting synthetic monitor results"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        monitor_guid = self._require_guid(arguments, "monitor_guid")
        hours = InputValidator.validate_time_range(arguments.get("hours", 24))

        data = self._unwrap(
            await self.client.entities.get_synthetic_results(account_id, monitor_guid, hours),
            f"getting synthetic results for {monitor_guid}",
        )

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
                status = "PASS" if r.get("result") == "SUCCESS" else "FAIL"
                duration = r.get("duration", "?")
                location = r.get("locationLabel", "?")
                error = r.get("error", "")
                line = f"  {status} {location} ({duration}ms)"
                if error:
                    line += f" -- {error}"
                lines.append(line)
        else:
            lines.append(f"No check results found in the last {hours}h.")

        return self._create_success_response("\n".join(lines))
