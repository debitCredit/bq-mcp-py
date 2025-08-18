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
    return any(keyword in query.upper() for keyword in DANGEROUS_KEYWORDS)


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
        Query results (user approval required for dangerous operations via MCP sampling)
    """
    # First, always run dry-run to validate syntax and estimate cost
    dry_run_result = await run_command(
        [
            "bq",
            "query",
            "--dry_run",
            "--format=json",
            f"--project_id={project_id}",
            "--use_legacy_sql=false",
            query,
        ]
    )

    if not dry_run_result["success"]:
        return f"Query validation failed: {dry_run_result['stderr']}"

    # Parse dry-run results to show cost estimation
    import json

    try:
        dry_run_data = json.loads(dry_run_result["stdout"])
        stats = dry_run_data.get("statistics", {}).get("query", {})
        bytes_processed = int(stats.get("totalBytesProcessed", 0))
        bytes_billed = int(stats.get("totalBytesBilled", 0))

        mb_processed = bytes_processed / 1024 / 1024
        cost_info = (
            f"Estimated bytes processed: {bytes_processed:,} ({mb_processed:.2f} MB)"
        )
        if bytes_billed > 0:
            mb_billed = bytes_billed / 1024 / 1024
            cost_info += f"\nBytes billed: {bytes_billed:,} ({mb_billed:.2f} MB)"
    except Exception:
        cost_info = "Could not parse cost estimation"

    # Check if query is dangerous and request user approval via MCP sampling
    if is_dangerous_query(query):
        approval_prompt = (
            f"⚠️  DANGEROUS QUERY DETECTED\n\n"
            f"Query: {query}\n\n"
            f"Project: {project_id}\n\n"
            f"{cost_info}\n\n"
            f"This query contains potentially destructive operations "
            f"({', '.join(kw for kw in DANGEROUS_KEYWORDS if kw in query.upper())}). "
            f"Should this query be executed?"
        )

        try:
            # Request user approval through MCP sampling
            sample_result = await ctx.sample(
                approval_prompt,
                system_prompt=(
                    "You are helping review a dangerous BigQuery operation. "
                    "Respond 'APPROVE' to proceed or 'DENY' to cancel."
                ),
                temperature=0.1,
                max_tokens=50,
            )

            if hasattr(sample_result, "text") and sample_result.text:
                response_text = sample_result.text.strip().upper()
                if "APPROVE" not in response_text:
                    return "Query execution cancelled by user."
            else:
                return "Query execution cancelled by user."

        except Exception as e:
            return f"Query execution cancelled: {str(e)}"

    # For safe queries, show cost info
    else:
        print(f"Query cost estimation: {cost_info}")

    # Execute the query
    result = await run_command(
        [
            "bq",
            "query",
            "--format=json",
            f"--project_id={project_id}",
            "--use_legacy_sql=false",
            query,
        ]
    )

    if not result["success"]:
        return f"Query execution failed: {result['stderr']}"

    return str(result["stdout"])


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
