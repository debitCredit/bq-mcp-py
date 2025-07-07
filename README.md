# BigQuery MCP Server

A minimal MCP (Model Context Protocol) server that provides passthrough access to Google Cloud BigQuery commands. This server uses your existing `gcloud` CLI authentication and provides tools for querying BigQuery table schemas.

## Features

- **Minimal setup**: Uses your existing `gcloud` CLI authentication
- **Schema inspection**: Get BigQuery table schemas in JSON format
- **Passthrough commands**: Direct access to `bq` and `gcloud` commands

## Prerequisites

- Google Cloud SDK (`gcloud` and `bq` commands) installed and configured
- Python 3.13+
- `uv` package manager

## Installation for Claude Code

Add this MCP server to Claude Code:

```bash
claude mcp add bq-mcp -- uv run /path/to/bq-mcp-py/bq-mcp.py
```

## Usage

Once installed, the server provides the following tools:

- `get_bq_schema(table_id)`: Get the schema for a BigQuery table in `project.dataset.table` format

## Authentication

This server uses your existing `gcloud` CLI authentication. Make sure you're authenticated with Google Cloud:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```