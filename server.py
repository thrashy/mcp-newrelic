#!/usr/bin/env python3
"""
New Relic MCP Server entry-point shim.

Kept so existing MCP client configs pointing at server.py keep working;
the implementation lives in newrelic_mcp.cli (also exposed as the
`newrelic-mcp` console script).
"""

from newrelic_mcp.cli import main

if __name__ == "__main__":
    main()
