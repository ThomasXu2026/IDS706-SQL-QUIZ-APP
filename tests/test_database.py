
import os
import psycopg

# Connect to Supabase using GitHub Secrets
with psycopg.connect(
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    sslmode="require",
    connect_timeout=15
) as conn:

    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")

        # Verify the database role
        cur.execute("SELECT current_user")
        role = cur.fetchone()[0]

        assert role == "quiz_reader", f"Unexpected role: {role}"
        print(f"Connected as: {role}")

        # Verify the practice tables
        expected = {
            "customers": 5,
            "products": 6,
            "orders": 10,
            "order_items": 16
        }

        for table, expected_count in expected.items():
            cur.execute(
                f"SELECT COUNT(*) FROM public.{table}"
            )
            actual_count = cur.fetchone()[0]

            assert actual_count == expected_count, (
                f"{table}: expected {expected_count}, "
                f"got {actual_count}"
            )

            print(f"{table}: {actual_count} rows - PASS")

        # Verify that the role cannot insert data
        cur.execute("""
            SELECT has_table_privilege(
                current_user,
                'public.products',
                'INSERT'
            )
        """)

        assert cur.fetchone()[0] is False
        print("Read-only permission: PASS")

print("All database tests passed!")
