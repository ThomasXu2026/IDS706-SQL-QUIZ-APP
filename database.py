"""Safe, read-only PostgreSQL execution and result grading helpers."""

from decimal import Decimal

import psycopg
from sqlglot import exp, parse


MAX_QUERY_LENGTH = 3000
MAX_ROWS = 100


def validate_read_only_sql(query: str) -> str:
    """Return a normalized query when it is one read-only PostgreSQL query."""
    query = query.strip()
    if not query:
        raise ValueError("Please enter a SQL query.")
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError("Query is too long.")

    # Parse the PostgreSQL AST instead of trusting a string prefix such as SELECT.
    try:
        statements = [statement for statement in parse(query, read="postgres") if statement]
    except Exception as exc:
        raise ValueError("The SQL could not be parsed.") from exc

    if len(statements) != 1:
        raise ValueError("Only one SQL statement is allowed.")

    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise ValueError("Only SELECT queries are allowed.")

    forbidden_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Command,
        exp.Merge,
        exp.Into,
    )
    if any(tree.find(node_type) is not None for node_type in forbidden_nodes):
        raise ValueError("Only read-only SELECT queries are allowed.")

    return query


def run_sql(query, secrets):
    """Execute one validated query using the configured read-only database role."""
    query = validate_read_only_sql(query)

    # The database role is read-only too; this transaction setting is defense in
    # depth for both student-written SQL and LLM-generated SQL.
    with psycopg.connect(
        host=secrets["DB_HOST"],
        port=secrets["DB_PORT"],
        dbname=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"],
        sslmode="require",
        connect_timeout=10,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(query, prepare=True)
            columns = [col.name for col in cur.description]
            rows = cur.fetchmany(MAX_ROWS + 1)

    return columns, rows[:MAX_ROWS], len(rows) > MAX_ROWS


def normalize_value(value):
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value))
    return value


def check_result(question, columns, rows, truncated):
    """Compare columns, ordered rows, and values with a quiz expectation."""
    expected = question["expected"]
    expected_columns = list(expected[0].keys())

    if columns != expected_columns or truncated or len(rows) != len(expected):
        return False

    for actual_row, expected_row in zip(rows, expected):
        actual_values = [normalize_value(value) for value in actual_row]
        expected_values = [
            normalize_value(expected_row[column]) for column in expected_columns
        ]
        if actual_values != expected_values:
            return False

    return True
