import subprocess
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bq-mcp", description="BigQuery MCP server for getting table schemas and routine information. Use get_bq_schema for tables/views and get_bq_routine for TVFs, stored procedures, and functions. When analyzing SQL queries with mixed identifiers, check both table and routine endpoints to identify the correct object type.")


async def run_command(command: list[str]) -> Dict[str, Any]:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "stdout": e.stdout,
            "stderr": e.stderr,
            "returncode": e.returncode
        }


@mcp.tool()
async def get_bq_schema(table_id: str) -> str:
    """
    Get BigQuery table schema for a given table ID.
    
    Args:
        table_id: Full table ID in format project.dataset.table
        
    Returns:
        JSON schema of the BigQuery table
    """
    parts = table_id.split('.')
    if len(parts) < 3:
        return "Error: table_id must be in format project.dataset.table"

    project_id = parts[0]
    dataset_table_id = '.'.join(parts[1:])

    bq_result = await run_command([
        "bq", "--project_id", project_id, "show", "--format=json", dataset_table_id
    ])

    if not bq_result["success"]:
        return f"Error getting BigQuery schema: {bq_result['stderr']}"

    return bq_result["stdout"]


@mcp.tool()
async def get_bq_routine(routine_id: str) -> str:
    """
    Get BigQuery routine (TVF, stored procedure, function) information for a given routine ID.
    
    Args:
        routine_id: Full routine ID in format project.dataset.routine_name
        
    Returns:
        JSON information about the BigQuery routine including definition, parameters, and return type
    """
    parts = routine_id.split('.')
    if len(parts) < 3:
        return "Error: routine_id must be in format project.dataset.routine_name"

    project_id = parts[0]
    dataset_routine_id = '.'.join(parts[1:])

    bq_result = await run_command([
        "bq", "--project_id", project_id, "show", "--routine", "--format=json", dataset_routine_id
    ])

    if not bq_result["success"]:
        return f"Error getting BigQuery routine information: {bq_result['stderr']}"

    return bq_result["stdout"]


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
