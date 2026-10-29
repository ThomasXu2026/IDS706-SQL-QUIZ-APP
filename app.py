
import psycopg
import streamlit as st
from datetime import datetime, timezone
from supabase import create_client
from database import check_result, run_sql
from questions import QUESTIONS
from rag import RAGService, suggested_question_id

st.set_page_config(
    page_title="SQL Quiz",
    page_icon="📚"
)

st.title("SQL Quiz")
st.write("Welcome to the Online Store SQL Quiz!")


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


@st.cache_resource(show_spinner=False)
def get_rag_service(api_key, model):
    return RAGService(api_key=api_key, generation_model=model)


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
    login_tab, signup_tab = st.tabs(["Sign In", "Sign Up"])

    # Sign in with an existing account
    with login_tab:
        st.subheader("Sign In")

        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input(
                "Password", type="password"
            )
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
                st.error("Invalid email or password.")

    # Register a new account
    with signup_tab:
        st.subheader("Create Account")

        with st.form("signup"):
            new_email = st.text_input("Email Address")
            new_password = st.text_input(
                "Password", type="password"
            )
            confirm_password = st.text_input(
                "Confirm Password", type="password"
            )
            signup = st.form_submit_button("Create Account")

        if signup:
            if not new_email.strip():
                st.warning("Please enter an email address.")

            elif len(new_password) < 8:
                st.warning("Password must have at least 8 characters.")

            elif new_password != confirm_password:
                st.error("Passwords do not match.")

            else:
                try:
                    response = supabase.auth.sign_up({
                        "email": new_email.strip(),
                        "password": new_password
                    })

                    if response.session:
                        st.success("Account created successfully!")
                        st.rerun()

                    elif response.user:
                        st.success(
                            "Registration submitted. "
                            "Please check your email to confirm "
                            "your account, then sign in."
                        )

                except Exception:
                    st.error(
                        "Registration failed. "
                        "Please check the email settings."
                    )

    st.stop()


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
            columns, rows, truncated = run_sql(sql_query, st.secrets)
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
            columns, rows, truncated = run_sql(sql_query, st.secrets)
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
                    columns, rows, truncated = run_sql(saved_sql, st.secrets)

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

    # RAG Text-to-SQL assistant
    st.divider()
    st.header("RAG Text-to-SQL Assistant")
    st.write(
        "Ask a question in plain English. The assistant retrieves relevant "
        "schema, business definitions, and solved examples from ChromaDB before "
        "Gemini generates PostgreSQL."
    )

    gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
    generation_model = st.secrets.get("GEMINI_MODEL", "gemini-3.8-flash")

    if not gemini_api_key:
        st.info(
            "The RAG assistant is unavailable because GEMINI_API_KEY is not "
            "configured in this deployment's secrets."
        )
    else:
        with st.form("rag_generation"):
            # Preload the currently selected quiz prompt so the required
            # quiz-question-to-SQL workflow is immediately testable.
            natural_language_question = st.text_area(
                "Natural-language database question",
                value=question["description"],
                placeholder=(
                    "Example: Which customers placed more than two orders?"
                ),
                height=100,
            )
            validation_options = ["Auto-detect", "No validation"] + [
                f"Q{index}: {question['title']}"
                for index, question in enumerate(QUESTIONS, start=1)
            ]
            validation_choice = st.selectbox(
                "Expected result for verification",
                validation_options,
                help=(
                    "Auto-detect uses the closest retrieved solved example. "
                    "Choose a quiz question when you want an exact target."
                ),
            )
            generate_clicked = st.form_submit_button(
                "Retrieve Context and Generate SQL",
                type="primary",
                use_container_width=True,
            )

        if generate_clicked:
            try:
                if not natural_language_question.strip():
                    raise ValueError(
                        "Please enter a natural-language question."
                    )
                with st.spinner("Retrieving evidence and generating SQL..."):
                    service = get_rag_service(
                        gemini_api_key,
                        generation_model,
                    )
                    retrieved = service.retrieve(natural_language_question)
                    draft = service.generate_sql(
                        natural_language_question,
                        retrieved,
                    )
                if validation_choice == "Auto-detect":
                    target_id = suggested_question_id(retrieved)
                elif validation_choice == "No validation":
                    target_id = None
                else:
                    target_id = validation_options.index(validation_choice) - 1

                st.session_state.rag_draft = draft
                st.session_state.rag_target_id = target_id
            except ValueError as error:
                st.warning(str(error))
            except Exception:
                st.error(
                    "RAG generation failed. Check the Gemini service and try again."
                )

        draft = st.session_state.get("rag_draft")
        if draft:
            st.subheader("Generated SQL")
            st.code(draft.sql, language="sql")
            st.caption(draft.explanation)

            with st.expander("Retrieved ChromaDB evidence", expanded=True):
                for index, document in enumerate(draft.retrieved, start=1):
                    st.markdown(
                        f"**{index}. {document.title}** — `{document.kind}` "
                        f"(distance {document.distance:.3f})"
                    )
                    st.write(document.content)

            target_id = st.session_state.get("rag_target_id")
            if target_id:
                st.info(
                    f"Execution will be verified against Q{target_id}: "
                    f"{QUESTIONS[target_id - 1]['title']}."
                )
            else:
                st.info(
                    "No expected result is selected; execution results will still "
                    "be displayed."
                )

            if st.button(
                "Run Generated SQL and Verify",
                use_container_width=True,
            ):
                try:
                    columns, rows, truncated = run_sql(draft.sql, st.secrets)
                    display_result(columns, rows, truncated)
                    if target_id:
                        if check_result(
                            QUESTIONS[target_id - 1],
                            columns,
                            rows,
                            truncated,
                        ):
                            st.success("Generated SQL matches the expected result.")
                        else:
                            st.warning(
                                "Generated SQL ran safely, but its output does not "
                                "match the selected expected result."
                            )
                except ValueError as error:
                    st.warning(str(error))
                except psycopg.Error as error:
                    show_sql_error(error)
                except Exception:
                    st.error("Unable to run the generated query.")

    # Log out and clear local answers
    st.divider()

    if st.button("Log Out"):
        supabase.auth.sign_out()

        for key in list(st.session_state.keys()):
            if key.startswith("answer_"):
                del st.session_state[key]

        st.rerun()
