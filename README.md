# BigQuery MCP Server

A minimal MCP (Model Context Protocol) server that provides passthrough access to Google Cloud BigQuery commands. This server uses your existing `gcloud` CLI authentication and provides tools for querying BigQuery table schemas and routine information.

## Features

- **Minimal setup**: Uses your existing `gcloud` CLI authentication
- **Schema inspection**: Get BigQuery table and view schemas in JSON format
- **Routine information**: Get BigQuery routine (TVF, stored procedure, function) details
- **Passthrough commands**: Direct access to `bq` and `gcloud` commands

## Prerequisites

- Google Cloud SDK (`gcloud` and `bq` commands) installed and configured
- Python 3.13+
- `uv` package manager

## Installation for coding agents

Add this MCP server to Claude Code user settings:

```bash
claude mcp add -s user bq-mcp -- uv --directory /path/to/bq-mcp-py/ run bq-mcp.py
```

Add this to Gemini CLI ~/.gemini/settings.json settings:

```json
"bq-mcp": {
  "command": "uv",
  "args": [
    "--directory",
    "/path/to/bq-mcp-py",
    "run",
    "bq-mcp.py"
  ]
}
```

Add this to VS Code user settings:

```json
"mcp": {
    "servers": {
    "bq-schema": {
        "type": "stdio",
        "command": "uv",
        "args": [
            "--directory",
            "/path/to/bq-mcp-py",
            "run",
            "bq-mcp.py"
        ]
    }
    }
}
```

## Usage

Once installed, the server provides the following tools:

- `get_bq_schema(table_id)`: Get the schema for a BigQuery table or view in `project.dataset.table` format
- `get_bq_routine(routine_id)`: Get information about a BigQuery routine (TVF, stored procedure, function) in `project.dataset.routine_name` format

## Authentication

This server uses your existing `gcloud` CLI authentication. Make sure you're authenticated with Google Cloud:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```
