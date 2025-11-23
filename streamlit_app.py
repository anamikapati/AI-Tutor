import streamlit as st
import requests

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Agentic AI Tutor", layout="wide")
st.title("Agentic AI Tutor")

# -------------------------------------------------
# Authentication
# -------------------------------------------------
if "student_id" not in st.session_state:
    st.session_state.student_id = None

st.sidebar.header("Account")

student_id_input = st.sidebar.text_input("Student ID")
student_name_input = st.sidebar.text_input("Name (only for registration)")

col1, col2 = st.sidebar.columns(2)

# Register
with col1:
    if st.button("Register"):
        if not student_id_input.strip() or not student_name_input.strip():
            st.sidebar.error("Enter both Student ID and Name")
        else:
            try:
                r = requests.post(f"{BASE_URL}/register_student",
                                  params={"student_id": student_id_input,
                                          "name": student_name_input})
                st.sidebar.success("Registered successfully")
            except:
                st.sidebar.error("Registration failed")

# Login
with col2:
    if st.button("Login"):
        if not student_id_input.strip():
            st.sidebar.error("Enter Student ID")
        else:
            try:
                r = requests.get(f"{BASE_URL}/progress/{student_id_input}")
                if r.status_code == 200:
                    st.session_state.student_id = student_id_input
                    st.sidebar.success(f"Logged in as {student_id_input}")
                else:
                    st.sidebar.error("Student not found")
            except:
                st.sidebar.error("Login failed")

if not st.session_state.student_id:
    st.warning("Login to continue")
    st.stop()

# -------------------------------------------------
# Ask Tutor Section
# -------------------------------------------------
st.header("Ask the Tutor")

query_text = st.text_input("Ask a question about any topic")

if st.button("Ask"):
    if not query_text.strip():
        st.error("Enter a question")
    else:
        try:
            r = requests.get(f"{BASE_URL}/ask",
                             params={"student_id": st.session_state.student_id,
                                     "query": query_text})
            st.session_state.ask_response = r.json()
        except Exception as e:
            st.error(f"Failed: {e}")
            st.session_state.ask_response = None

# -------------------------------------------------
# Explanation + Quiz
# -------------------------------------------------
if "ask_response" in st.session_state and st.session_state.ask_response:

    data = st.session_state.ask_response

    if data.get("action") == "explain":

        st.subheader("Explanation")
        st.write(data.get("answer", ""))
        st.caption(f"Source: {data.get('chapter', 'N/A')}")
        st.caption(f"Recommended difficulty: {data.get('difficulty', 'medium')}")

        # Fetch quiz for same topic
        try:
            q = requests.get(
                f"{BASE_URL}/quiz",
                params={
                    "student_id": st.session_state.student_id,
                    "topic": data.get("topic", ""),
                    "difficulty": data.get("difficulty", "medium")
                }
            ).json().get("quiz", [])
        except:
            q = []

        if q:
            st.subheader("Quiz")

            answers = {}

            for idx, item in enumerate(q, start=1):
                st.markdown(f"Q{idx}. {item['question']}")

                options = item.get("options", [])

                # Unique stable key per question
                key = f"quiz_{st.session_state.student_id}_{idx}"

                selected = st.radio(
                    "",
                    options,
                    index=None,
                    key=key
                )

                answers[idx] = selected

                st.write("")  # spacing

            if st.button("Submit Quiz"):
                correct = 0
                total = 0

                for idx, item in enumerate(q, start=1):
                    user_choice = answers[idx]
                    opt_list = item.get("options", [])
                    ans_letter = item.get("answer")

                    if opt_list and ans_letter:
                        total += 1
                        correct_value = opt_list[ord(ans_letter) - 65]
                        if user_choice == correct_value:
                            correct += 1

                    # log attempt
                    try:
                        requests.post(
                            f"{BASE_URL}/submit_answer",
                            params={
                                "student_id": st.session_state.student_id,
                                "topic": data.get("topic", ""),
                                "question": item.get("question", ""),
                                "selected_option": user_choice or "",
                                "correct_option": ans_letter,
                                "difficulty": data.get("difficulty", "medium")
                            }
                        )
                    except:
                        pass

                if total > 0:
                    st.success(f"Your Score: {correct}/{total}")
                else:
                    st.info("Quiz submitted")

    else:
        st.write("Unexpected response format")
