# New Relic MCP Server

[![CI](https://github.com/thrashy/mcp-newrelic/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/thrashy/mcp-newrelic/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/type--checked-mypy-blue.svg)](https://mypy-lang.org/)

A comprehensive Model Context Protocol (MCP) server for New Relic monitoring, observability, and management operations.

## Features

### Core Monitoring & Observability
- **NRQL Query Execution**: Run custom New Relic Query Language queries
- **Application Performance**: Real-time performance metrics (response time, throughput, Apdex)
- **Error Monitoring**: Error rates, counts, and detailed error analysis
- **Infrastructure Monitoring**: Host metrics, CPU, memory, disk usage
- **Incident Management**: Recent incidents, violations, and alert status

### Dashboard Management
- **Dashboard Operations**: Create, read, update, and delete dashboards
- **Widget Management**: Add, update, and remove dashboard widgets with rawConfiguration support for dual y-axis, fixed y-axis ranges, legend control, and chart styles
- **Search & Discovery**: Find dashboards by name or GUID
- **Visualization Support**: Line charts, bar charts, pie charts, tables, billboards

### Entity Management
- **Entity Search**: Find any New Relic entity (APM apps, hosts, synthetic monitors, browsers) by name, type, domain, or tags
- **Entity Tagging**: Add, update, and delete tags on any entity
- **Service Levels**: List all SLIs/SLOs with compliance data and objectives
- **Synthetic Monitors**: List monitors with status, success rate, and location health; query recent check results

### Alert & Notification System
- **Alert Policies**: Create and manage alert policies with configurable incident preferences
- **NRQL Conditions**: Set up custom alert conditions with thresholds and triggers
- **Notification Destinations**: Configure email, Slack, webhook, PagerDuty integrations
- **Notification Channels**: Link destinations to specific notification preferences
- **Workflows**: Connect alert policies to notification channels with filtering

### Deployment Tracking
- **Deployment Markers**: Track deployment events and their impact
- **Release Correlation**: Correlate performance changes with deployments

## Installation

### Prerequisites
- **Python 3.11+** (recommended: use `uv` for fast dependency management)
- **New Relic User API Key** (not Ingest key)
- **New Relic Account ID**

### Quick Start
```bash
# Clone the repository
git clone <repository-url>
cd mcp-newrelic

# Install dependencies (using uv - recommended)
uv sync

# Or using pip
pip install -e .

# Configure your credentials (see Configuration section below)
```

## Setup

### Getting Your Credentials

1. **API Key**: Go to [New Relic API Keys](https://one.newrelic.com/api-keys) → Create User API Key
2. **Account ID**: Found in your New Relic URL: `https://one.newrelic.com/accounts/{ACCOUNT_ID}/...`
3. **Region**: Use "EU" if your account is on `one.eu.newrelic.com`, otherwise "US"

### MCP Client Integration

Add the server to your MCP client config. **You do not need to start the server manually** — your MCP client launches it automatically.

```json
{
  "mcpServers": {
    "newrelic": {
      "command": "uv",
      "args": ["run", "python", "/path/to/mcp-newrelic/server.py"],
      "env": {
        "NEW_RELIC_API_KEY": "your-api-key",
        "NEW_RELIC_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

Where this config lives depends on your client (e.g., `~/.claude.json` for Claude Code, `claude_desktop_config.json` for Claude Desktop, `.cursor/mcp.json` for Cursor, etc.). Replace `/path/to/mcp-newrelic/server.py` with the actual path to your clone.

### Advanced Configuration

If you need to run the server manually (e.g., for development or debugging), it supports flexible configuration with clear precedence (highest to lowest):

#### 1. Command Line Arguments (Highest Priority)
```bash
uv run python server.py \
  --api-key "NRAK-your-api-key" \
  --account-id "your-account-id" \
  --region "US"
```

#### 2. JSON Configuration File
```bash
# Copy and edit the example config
cp newrelic-config.json.example config/newrelic-config.json

# Run with config file
uv run python server.py --config config/newrelic-config.json
```

Example `newrelic-config.json`:
```json
{
  "api_key": "NRAK-your-api-key",
  "account_id": "your-account-id",
  "region": "US",
  "timeout": 30
}
```

#### 3. Environment Variables (Lowest Priority)
```bash
export NEW_RELIC_API_KEY="NRAK-your-api-key"
export NEW_RELIC_ACCOUNT_ID="your-account-id"
export NEW_RELIC_REGION="US"  # US or EU
export NEW_RELIC_TIMEOUT="30"
```
```

## Available Tools

### NRQL & Monitoring
- **`query_nrql`**: Execute custom NRQL queries with full flexibility
- **`get_app_performance`**: Application performance metrics (avg/p95 response time, throughput, Apdex)
- **`get_app_errors`**: Error metrics, counts, and error analysis
- **`get_incidents`**: Recent incidents with time filtering
- **`get_infrastructure_hosts`**: Infrastructure host metrics (CPU, memory, disk)
- **`get_alert_violations`**: Recent alert violations and status
- **`get_deployments`**: Deployment markers and impact analysis

### Dashboard Management
- **`get_dashboards`**: List and search dashboards with filtering
- **`search_all_dashboards`**: Advanced dashboard search with local filtering
- **`get_dashboard_widgets`**: Retrieve all widgets from a dashboard
- **`create_dashboard`**: Create new dashboards for monitoring
- **`delete_dashboard`**: Delete a dashboard by GUID
- **`add_widget_to_dashboard`**: Add custom NRQL-based widgets
- **`update_widget`**: Update existing dashboard widgets
- **`delete_widget`**: Remove widgets from dashboards

### Entity Management
- **`entity_search`**: Search for any entity by name, type (APPLICATION, HOST, MONITOR, KEY_TRANSACTION), or domain (APM, INFRA, SYNTH, BROWSER, EXT). Supports `limit` (default 25, max 200) and `minimal_output` to reduce response size.
- **`get_entity`**: Look up a single entity by GUID with full details (name, type, account, tags, permalink, type-specific metadata)
- **`decode_entity_guid`**: Decode a base64-encoded entity GUID to reveal account ID, domain, entity type, and domain ID without an API call
- **`get_entity_tags`**: Get all tags for an entity by GUID
- **`add_tags_to_entity`**: Add or update key-value tags on an entity
- **`replace_tags_on_entity`**: Replace all tags on an entity (overwrites existing)
- **`delete_tags_from_entity`**: Remove tag keys from an entity
- **`delete_tag_values`**: Delete specific tag key-value pairs from an entity
- **`list_service_levels`**: List all SLIs/SLOs with compliance data and objectives
- **`list_synthetic_monitors`**: List all synthetic monitors with status, success rate, and location health
- **`get_synthetic_results`**: Get recent pass/fail check results per location for a specific monitor

### Alert & Notification Management
- **`create_alert_policy`**: Create alert policies with incident preferences
- **`update_alert_policy`**: Update an existing alert policy
- **`delete_alert_policy`**: Delete an alert policy by ID
- **`create_nrql_condition`**: Create NRQL-based alert conditions
- **`update_nrql_condition`**: Update an existing NRQL alert condition
- **`delete_nrql_condition`**: Delete a NRQL alert condition by ID
- **`create_notification_destination`**: Set up notification endpoints (email, Slack, webhook, PagerDuty)
- **`delete_notification_destination`**: Delete a notification destination by ID
- **`create_notification_channel`**: Create notification channels
- **`create_workflow`**: Connect alerts to notifications with filtering
- **`delete_workflow`**: Delete a workflow by ID
- **`list_alert_policies`**: List all alert policies
- **`list_alert_conditions`**: List alert conditions with optional filters by policy, name, or NRQL query
- **`list_notification_destinations`**: List all notification destinations
- **`list_notification_channels`**: List all notification channels
- **`list_workflows`**: List all alert workflows

## MCP Resources

Access structured data through these MCP resources:

- **`newrelic://applications`**: Complete list of monitored applications
- **`newrelic://incidents/recent`**: Recent incidents and alert summary
- **`newrelic://dashboards`**: Dashboard metadata and widgets
- **`newrelic://alerts/policies`**: Alert policies and configurations
- **`newrelic://alerts/conditions`**: Alert conditions across all policies
- **`newrelic://alerts/workflows`**: Workflow configurations and notifications

## Architecture

### Design
- **Strategy Pattern**: Tool handlers using pluggable strategy implementations
- **Composition**: `NewRelicClient` composes specialized sub-clients (`monitoring`, `alerts`, `dashboards`, `entities`) instead of using multiple inheritance
- **Configuration**: Hierarchical config (CLI > file > env vars) with validation
- **Error Handling**: Typed `ApiError` dataclass for consistent error propagation
- **Pagination**: Cursor-based pagination for NerdGraph queries (entity search, alert policies, conditions, service levels, synthetic monitors)

### Key Components
- **`NewRelicClient`**: Unified client composing all specialized sub-clients
- **`AlertsClient`**: Alert policies, conditions, and notification management
- **`DashboardsClient`**: Dashboard and widget operations
- **`EntitiesClient`**: Entity search, tagging, service levels, and synthetic monitors
- **`MonitoringClient`**: NRQL queries and performance monitoring
- **`ToolHandlers`**: Strategy-based dispatcher for MCP tool calls
- **`ResourceHandlers`**: MCP resource operations and data formatting

## Docker Support

### Quick Docker Run
```bash
docker build -t newrelic-mcp-server .

docker run -e NEW_RELIC_API_KEY=your-key \
           -e NEW_RELIC_ACCOUNT_ID=your-id \
           newrelic-mcp-server
```

### Docker Compose (Recommended)
```bash
# Setup environment
cp .env.example .env
# Edit .env with your New Relic credentials

# Build and run
docker-compose up --build

# Run in background
docker-compose up -d --build
```

### Production Deployment
The Docker image uses:
- **Multi-stage build** for optimized image size
- **Non-root user** for security
- **Volume mounts** for configuration and logs
- **Health checks** for container monitoring

## Development

### Development Setup
```bash
# Install development dependencies
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Run quality checks
uv run ruff check .          # Linting
uv run ruff format .         # Formatting  
uv run mypy newrelic_mcp/    # Type checking
uv run pylint newrelic_mcp/  # Additional analysis
```

### Code Quality
This project maintains high code quality with:
- **Ruff**: Fast linting and formatting
- **MyPy**: Static type checking
- **Pylint**: Additional code analysis
- **Pre-commit hooks**: Automated quality checks
- **Comprehensive type annotations**: Full type coverage

### Testing
```bash
# Run all tests
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v
```

For detailed development information, see [**DEVELOPMENT.md**](DEVELOPMENT.md).

## Example Usage

### Complete Alert Setup Workflow
```python
# 1. Create alert policy
create_alert_policy(name="High CPU Usage Policy")

# 2. Create NRQL condition  
create_nrql_condition(
    policy_id="policy-id-from-step-1",
    name="High CPU Alert",
    nrql_query="SELECT average(cpuPercent) FROM SystemSample",
    threshold=80
)

# 3. Create notification destination
create_notification_destination(
    name="Team Email",
    type="EMAIL", 
    properties={"email": "alerts@company.com"}
)

# 4. Create notification channel
create_notification_channel(
    name="CPU Alert Channel",
    destination_id="destination-id-from-step-3",
    type="EMAIL"
)

# 5. Create workflow
create_workflow(
    name="CPU Alert Workflow",
    channel_ids=["channel-id-from-step-4"]
)
```

## Requirements

- **Python**: 3.11 or higher
- **New Relic API Key**: User API key (starts with `NRAK-` or `NRAA-`)
- **New Relic Account**: Valid account with appropriate permissions
- **Dependencies**: Managed automatically with `uv` or `pip`

## License

This project is licensed under the **MIT License**. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please:

1. Read [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions
2. Follow the established code style and quality standards
3. Add tests for new functionality
4. Update documentation as needed

## Support

- **Documentation**: Check [DEVELOPMENT.md](DEVELOPMENT.md) for detailed guides
- **Issues**: Report bugs and feature requests via GitHub Issues
- **New Relic API**: [Official New Relic API Documentation](https://docs.newrelic.com/docs/apis/)
- **MCP Protocol**: [Model Context Protocol Specification](https://modelcontextprotocol.io/)