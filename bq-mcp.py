import hashlib
import subprocess
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp: FastMCP = FastMCP(
    "bq-mcp",
    description=(
        "BigQuery MCP server for getting table schemas and routine information. "
        "Use get_bq_schema for tables/views and get_bq_routine for TVFs, stored "
        "procedures, and functions. When analyzing SQL queries with mixed "
        "identifiers, check both table and routine endpoints to identify the "
        "correct object type."
    ),
)

# Security configuration
CONFIRMATION_TOKENS: dict[str, dict[str, Any]] = {}
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


def generate_confirmation_token(query: str) -> str:
    """Generate time-limited confirmation token."""
    timestamp = str(int(time.time()))
    token = hashlib.sha256(f"{query}{timestamp}".encode()).hexdigest()[:16]
    CONFIRMATION_TOKENS[token] = {"query": query, "timestamp": int(timestamp)}
    return token


def validate_confirmation_token(token: str, query: str) -> bool:
    """Validate confirmation token is recent and matches query."""
    if token not in CONFIRMATION_TOKENS:
        return False

    token_data = CONFIRMATION_TOKENS[token]
    if time.time() - token_data["timestamp"] > 60:  # 60 second expiry
        del CONFIRMATION_TOKENS[token]
        return False

    return str(token_data["query"]) == query


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


@mcp.tool()
async def get_bq_schema(table_id: str) -> str:
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


@mcp.tool()
async def get_bq_routine(routine_id: str) -> str:
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


@mcp.tool()
async def execute_bq_query(
    query: str, project_id: str, confirmation_token: str | None = None
) -> str:
    """
    Execute BigQuery query with safety checks.

    Args:
        query: SQL query to execute
        project_id: Google Cloud project ID
        confirmation_token: Required for dangerous operations (DELETE, DROP, etc.)

    Returns:
        Query results or confirmation token requirement
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

    # Check if query is dangerous
    if is_dangerous_query(query):
        if not confirmation_token:
            token = generate_confirmation_token(query)
            return (
                f"⚠️  DANGEROUS QUERY DETECTED\n\n{cost_info}\n\n"
                f"To execute this query, call again with confirmation_token: {token}"
            )

        if not validate_confirmation_token(confirmation_token, query):
            return "Invalid or expired confirmation token. Please request a new one."

    # For safe queries, show cost info but proceed
    if not confirmation_token:
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
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
