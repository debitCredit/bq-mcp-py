import re
import subprocess
from typing import Any

from fastmcp import Context, FastMCP

mcp = FastMCP("bq-mcp")

# Security configuration
DANGEROUS_KEYWORDS = [
    "DELETE",
    "DROP",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "UPDATE",
    "INSERT",
]


def is_dangerous_query(query: str) -> bool:
    """Check if query contains dangerous operations."""
    query_upper = query.upper()
    # Use word boundaries to avoid false positives like 'created_at' containing 'CREATE'
    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", query_upper):
            return True
    return False


async def run_command(command: list[str]) -> dict[str, Any]:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"success": True, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "stdout": e.stdout,
            "stderr": e.stderr,
            "returncode": e.returncode,
        }


@mcp.tool
async def get_bq_schema(table_id: str, ctx: Context) -> str:
    """
    Get BigQuery table schema for a given table ID.

    Args:
        table_id: Full table ID in format project.dataset.table

    Returns:
        JSON schema of the BigQuery table
    """
    parts = table_id.split(".")
    if len(parts) < 3:
        return "Error: table_id must be in format project.dataset.table"

    project_id = parts[0]
    dataset_table_id = ".".join(parts[1:])

    bq_result = await run_command(
        ["bq", "--project_id", project_id, "show", "--format=json", dataset_table_id]
    )

    if not bq_result["success"]:
        return f"Error getting BigQuery schema: {bq_result['stderr']}"

    return str(bq_result["stdout"])


@mcp.tool
async def get_bq_routine(routine_id: str, ctx: Context) -> str:
    """
    Get BigQuery routine (TVF, stored procedure, function) information for a
    given routine ID.

    Args:
        routine_id: Full routine ID in format project.dataset.routine_name

    Returns:
        JSON information about the BigQuery routine including definition,
        parameters, and return type
    """
    parts = routine_id.split(".")
    if len(parts) < 3:
        return "Error: routine_id must be in format project.dataset.routine_name"

    project_id = parts[0]
    dataset_routine_id = ".".join(parts[1:])

    bq_result = await run_command(
        [
            "bq",
            "--project_id",
            project_id,
            "show",
            "--routine",
            "--format=json",
            dataset_routine_id,
        ]
    )

    if not bq_result["success"]:
        return f"Error getting BigQuery routine information: {bq_result['stderr']}"

    return str(bq_result["stdout"])


@mcp.tool
async def execute_bq_query(query: str, project_id: str, ctx: Context) -> str:
    """
    Execute BigQuery query with safety checks.

    Args:
        query: SQL query to execute
        project_id: Google Cloud project ID

    Returns:
        Query results (user approval required for dangerous operations via
        MCP elicitations)
    """
    # Check if query is dangerous and request user approval via MCP elicitations
    if is_dangerous_query(query):
        detected_keywords = [kw for kw in DANGEROUS_KEYWORDS if kw in query.upper()]
        operations = ", ".join(detected_keywords)
        approval_prompt = (
            f"⚠️  DANGEROUS QUERY DETECTED\n\n"
            f"Query: {query}\n\n"
            f"Project: {project_id}\n\n"
            f"This query contains potentially destructive operations ({operations}). "
            f"Please review carefully and decide whether to approve execution."
        )

        try:
            # Request user approval through MCP elicitations
            result = await ctx.elicit(message=approval_prompt, response_type=None)

            if result.action == "accept":
                # User approved the query - continue with execution
                pass
            elif result.action == "decline":
                return "Query execution declined by user."
            elif result.action == "cancel":
                return "Query execution cancelled by user."
            else:
                return "Query execution cancelled by user."

        except Exception as e:
            return f"Query execution cancelled: {str(e)}"

    # Execute the query
    bq_result = await run_command(
        [
            "bq",
            "query",
            "--format=json",
            f"--project_id={project_id}",
            "--use_legacy_sql=false",
            query,
        ]
    )

    if not bq_result["success"]:
        return f"Query execution failed: {bq_result['stderr']}"

    return str(bq_result["stdout"])


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
