
import psycopg
import streamlit as st
from decimal import Decimal
from datetime import datetime, timezone
from supabase import create_client
from questions import QUESTIONS

st.set_page_config(
    page_title="SQL Quiz",
    page_icon="📚"
)

st.title("SQL Quiz")
st.write("Welcome to the Online Store SQL Quiz!")


# Execute SQL using the read-only database role
def run_sql(query):
    query = query.strip()

    if not query:
        raise ValueError("Please enter a SQL query.")

    if len(query) > 3000:
        raise ValueError("Query is too long.")

    if not query.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")

    with psycopg.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        sslmode="require",
        connect_timeout=10
    ) as conn:

        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(query, prepare=True)

            columns = [col.name for col in cur.description]
            rows = cur.fetchmany(101)

    return columns, rows[:100], len(rows) > 100


# Normalize numeric values before comparison
def normalize_value(value):
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value))
    return value


# Compare query output with expected results
def check_result(question, columns, rows, truncated):
    expected = question["expected"]
    expected_columns = list(expected[0].keys())

    if columns != expected_columns:
        return False

    if truncated or len(rows) != len(expected):
        return False

    for actual_row, expected_row in zip(rows, expected):
        actual_values = [normalize_value(v) for v in actual_row]
        expected_values = [
            normalize_value(expected_row[col])
            for col in expected_columns
        ]

        if actual_values != expected_values:
            return False

    return True


# Display query results
def display_result(columns, rows, truncated):
    results = [
        dict(zip(columns, row))
        for row in rows
    ]

    st.success("Query executed successfully!")
    st.write(f"Rows displayed: {len(results)}")
    st.dataframe(results, use_container_width=True)

    if truncated:
        st.info("Only the first 100 rows are shown.")


# Display safe SQL errors
def show_sql_error(error):
    message = getattr(error.diag, "message_primary", None)
    st.error(message or "SQL query failed.")


# Create a Supabase client for this browser session
if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = st.session_state.supabase


# Check login status
try:
    response = supabase.auth.get_user()
    user = response.user
except Exception:
    user = None


# Show the login form
if user is None:
    st.subheader("Sign In")

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("Login")

    if login:
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user and response.session:
                st.rerun()
            else:
                st.error("Login failed.")

        except Exception:
            st.error("Login failed. Check your credentials.")

else:
    st.success(f"Logged in as {user.email}")

    st.subheader("Online Store SQL Quiz")
    st.write("Total Points: 20")

    # Select a quiz question
    question_index = st.selectbox(
        "Choose a Question",
        range(len(QUESTIONS)),
        format_func=lambda i: QUESTIONS[i]["title"]
    )

    question = QUESTIONS[question_index]

    st.divider()
    st.subheader(question["title"])
    st.write(f"**Points: {question['points']}**")
    st.write(question["description"])

    # Show the expected SQL and result
    with st.expander("Hint — Expected SQL and Result"):
        st.code(question["sql"], language="sql")
        st.write("Expected result:")
        st.table(question["expected"])

    # Load the saved answer from Supabase
    answer_key = f"answer_{user.id}_{question_index}"

    if answer_key not in st.session_state:
        try:
            response = (
                supabase.table("quiz_answers")
                .select("sql_query")
                .eq("user_id", str(user.id))
                .eq("question_id", question_index + 1)
                .limit(1)
                .execute()
            )

            saved_sql = (
                response.data[0]["sql_query"]
                if response.data else ""
            )

            st.session_state[answer_key] = saved_sql

        except Exception:
            st.error("Unable to load saved answer.")
            st.stop()

    # Display the SQL editor
    sql_query = st.text_area(
        "Write your SQL query:",
        height=180,
        key=answer_key,
        placeholder="SELECT ..."
    )

    # Display the action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        save_clicked = st.button(
            "Save Answer",
            use_container_width=True
        )

    with col2:
        run_clicked = st.button(
            "Run Query",
            type="primary",
            use_container_width=True
        )

    with col3:
        check_clicked = st.button(
            "Check Answer",
            use_container_width=True
        )

    # Save the current answer to Supabase
    if save_clicked:
        answer = sql_query.strip()

        if not answer:
            st.warning("Please write a SQL query first.")

        elif len(answer) > 3000:
            st.error("SQL query is too long.")

        else:
            try:
                supabase.table("quiz_answers").upsert(
                    {
                        "user_id": str(user.id),
                        "question_id": question_index + 1,
                        "sql_query": answer,
                        "updated_at": datetime.now(
                            timezone.utc
                        ).isoformat()
                    },
                    on_conflict="user_id,question_id"
                ).execute()

                st.success("Answer saved successfully!")

            except Exception:
                st.error("Failed to save answer.")

    # Run the SQL query and show results
    if run_clicked:
        try:
            columns, rows, truncated = run_sql(sql_query)
            display_result(columns, rows, truncated)

        except ValueError as e:
            st.warning(str(e))

        except psycopg.Error as e:
            show_sql_error(e)

        except Exception:
            st.error("Unable to run the query.")

    # Check the current answer against expected results
    if check_clicked:
        try:
            columns, rows, truncated = run_sql(sql_query)
            display_result(columns, rows, truncated)

            correct = check_result(
                question, columns, rows, truncated
            )

            if correct:
                st.success(
                    f"Correct! +{question['points']} points."
                )
            else:
                st.warning(
                    "Incorrect result. Score: 0 points. "
                    "Compare your result with the hint."
                )

        except ValueError as e:
            st.warning(str(e))

        except psycopg.Error as e:
            show_sql_error(e)

        except Exception:
            st.error("Unable to check the answer.")

    # Grade all saved answers
    st.divider()
    st.subheader("Quiz Results")

    if st.button("Grade All Saved Answers"):
        try:
            response = (
                supabase.table("quiz_answers")
                .select("question_id, sql_query")
                .eq("user_id", str(user.id))
                .execute()
            )

            saved_answers = {
                row["question_id"]: row["sql_query"]
                for row in response.data
            }

            total_score = 0
            summary = []

            for i, q in enumerate(QUESTIONS, start=1):
                saved_sql = saved_answers.get(i)

                if not saved_sql:
                    summary.append({
                        "Question": f"Q{i}",
                        "Points": 0,
                        "Status": "Not saved"
                    })
                    continue

                try:
                    columns, rows, truncated = run_sql(saved_sql)

                    correct = check_result(
                        q, columns, rows, truncated
                    )

                    points = q["points"] if correct else 0
                    total_score += points

                    summary.append({
                        "Question": f"Q{i}",
                        "Points": points,
                        "Status": "Correct" if correct else "Incorrect"
                    })

                except (ValueError, psycopg.Error):
                    summary.append({
                        "Question": f"Q{i}",
                        "Points": 0,
                        "Status": "SQL Error"
                    })

            st.metric("Total Score", f"{total_score} / 20")
            st.table(summary)

        except Exception:
            st.error("Unable to grade saved answers.")

    # Log out and clear local answers
    st.divider()

    if st.button("Log Out"):
        supabase.auth.sign_out()

        for key in list(st.session_state.keys()):
            if key.startswith("answer_"):
                del st.session_state[key]

        st.rerun()
