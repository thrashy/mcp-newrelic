"""Contract tests against a real New Relic account.

Mocked tests cannot catch the failure mode these cover: the code assuming an NRDB
attribute that does not exist. A hand-written fixture and the code under test share
the same wrong assumption, so both agree and the suite stays green while the tool
returns "Unknown" forever.

Run with:  RUN_LIVE_TESTS=1 NEW_RELIC_API_KEY=... NEW_RELIC_ACCOUNT_ID=... uv run pytest tests/test_live_contract.py
"""

import os

import pytest

from newrelic_mcp.client.unified_client import NewRelicClient
from newrelic_mcp.config import NewRelicConfig
from newrelic_mcp.utils.graphql_helpers import extract_nrql_results

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS") or not os.getenv("NEW_RELIC_API_KEY"),
    reason="live tests need RUN_LIVE_TESTS=1 and New Relic credentials",
)

# Every NRDB attribute the server reads. An entry here means some query filters on it
# or some formatter renders it, so if NRDB stops providing it the tool degrades silently.
REQUIRED_ATTRIBUTES = {
    "Transaction": ["appName", "duration"],
    "TransactionError": ["appName", "duration"],
    "Deployment": ["entity.name", "version", "timestamp", "description"],
    "NrAiIncident": ["event", "priority", "title", "entity.name", "targetName", "timestamp"],
    "SystemSample": ["hostname", "cpuPercent", "memoryUsedPercent", "diskUsedPercent"],
    "SyntheticCheck": ["result", "duration", "locationLabel"],
}


@pytest.fixture
def client():
    return NewRelicClient(NewRelicConfig.from_env())


@pytest.fixture
def account_id():
    return NewRelicConfig.from_env().account_id


@pytest.mark.parametrize("event_type,attributes", REQUIRED_ATTRIBUTES.items(), ids=list(REQUIRED_ATTRIBUTES))
async def test_required_attributes_exist(client, account_id, event_type, attributes):
    response = await client.base.query_nrql(account_id, f"SELECT keyset() FROM {event_type} SINCE 1 day ago")
    present = {row["key"] for row in extract_nrql_results(response)}
    assert present, f"{event_type} returned no schema; account may have no data for it"

    missing = [attribute for attribute in attributes if attribute not in present]
    assert not missing, f"{event_type} is missing {missing} - queries or formatters reading them yield null"


async def test_percentile_returns_nested_dict(client, account_id):
    """_format_duration unwraps this shape; a flat float would mean the unwrap is dead code."""
    response = await client.base.query_nrql(
        account_id,
        "SELECT percentile(duration, 95) AS p95 FROM Transaction SINCE 1 hour ago",
    )
    p95 = extract_nrql_results(response)[0]["p95"]
    assert isinstance(p95, dict), f"expected percentile dict, got {type(p95).__name__}"


async def test_transaction_duration_is_seconds(client, account_id):
    """_format_duration multiplies by 1000; that is only correct while NRQL reports seconds."""
    response = await client.base.query_nrql(
        account_id,
        "SELECT average(duration) AS avg FROM Transaction SINCE 1 hour ago",
    )
    average = extract_nrql_results(response)[0]["avg"]
    assert 0 < average < 60, f"average duration {average} is not plausible in seconds"
