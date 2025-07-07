import subprocess
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bq-mcp")


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
    # Parse table ID to extract project and dataset.table
    parts = table_id.split('.')
    if len(parts) < 3:
        return "Error: table_id must be in format project.dataset.table"

    project_id = parts[0]
    dataset_table_id = '.'.join(parts[1:])

    # Set gcloud project
    gcloud_result = await run_command([
        "gcloud", "config", "set", "project", project_id
    ])

    if not gcloud_result["success"]:
        return f"Error setting gcloud project: {gcloud_result['stderr']}"

    # Get BigQuery schema
    bq_result = await run_command([
        "bq", "show", "--format=prettyjson", dataset_table_id
    ])

    if not bq_result["success"]:
        return f"Error getting BigQuery schema: {bq_result['stderr']}"

    return bq_result["stdout"]


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
