import streamlit as st
import json
import os
from core import get_answer, make_api_request, CHAT_HISTORY_FILE

st.set_page_config(page_title="Chat Assistant", page_icon="🤖")

# ===== Debug UI flag =====
SHOW_DEBUG_UI = False  # Set to True to enable "Show Debug" buttons

# Initialize session state
default_repo_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(default_repo_path)

# Setup session state
if "chat_history" not in st.session_state:
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, 'r') as f:
            raw_data = json.load(f)

        # Group messages into pairs (user -> assistant)
        chat_history = []
        for i in range(0, len(raw_data) - 1, 2):
            user_msg = raw_data[i]["content"] if raw_data[i]["role"] == "user" else ""
            assistant_msg = raw_data[i + 1]["content"] if raw_data[i + 1]["role"] == "assistant" else ""
            answer = json.loads(assistant_msg)


            chat_history.append({
                "user": user_msg,
                "response": answer.get("answer"),
                "debug": {
                    "Endpoint": answer.get("endpoint"),
                    "Method": answer.get("method"),
                    "Parameters": json.dumps(answer.get("parameters", {}), indent=2),
                    "Ready": answer.get("ready"),
                    "Result": "No API call made." if not answer.get("ready") else "",
                },
            })

        st.session_state.chat_history = chat_history
    else:
        st.session_state.chat_history = []

if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

st.title("🤖 Request Chat Assistant")

# Show chat history
for i, msg in enumerate(st.session_state.chat_history):
    with st.chat_message("user"):
        st.markdown(f"**You:** {msg['user']}")

    with st.chat_message("assistant"):
        st.markdown(f"**Assistant:**\n{msg['response']}", unsafe_allow_html=True)

        if msg.get("file_data"):
            st.download_button(
                label="📄 Download API Response",
                data=msg["file_data"],
                file_name="api_response.json",
                mime="application/json",
                key=f"download_{i}"
            )

        # Inside chat history loop
        if msg.get("debug") and SHOW_DEBUG_UI:
            debug_key = f"debug_{i}"
            show_debug = st.toggle("🛠️ Show Debug", key=debug_key)
            if show_debug:
                for k, v in msg["debug"].items():
                    st.code(f"{k}: {v}", language="json")


# Chat input at the bottom
user_input = st.chat_input("Type your message here...")

# Save input temporarily to persist across reruns
if user_input:
    st.session_state.pending_input = user_input

if st.session_state.pending_input:
    user_input = st.session_state.pending_input
    st.session_state.pending_input = None  # Clear after processing

    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(f"**You:** {user_input}")

    # Get model response
    answer_str = get_answer(user_input)
    file_path = None
    file_data = None
    response_markdown = "*No answer provided.*"
    debug_data = None

    try:
        answer = json.loads(answer_str)
        response_markdown = answer.get("answer", "*⚠️ An error occurred. Please try again.*")
        endpoint = answer.get("endpoint")
        method = answer.get("method")
        payload = answer.get("parameters")
        ready = answer.get("ready")

        result_message = "No API call made."
        if ready and endpoint and method:
            result_message, file_path = make_api_request(endpoint, payload, method)

            if file_path:
                with open(file_path, "rb") as f:
                    file_data = f.read()
            else:
                response_markdown = f"{result_message}"

        debug_data = {
            "Endpoint": endpoint,
            "Method": method,
            "Parameters": json.dumps(payload, indent=2),
            "Ready": ready,
            "Result": result_message,
        }

    except json.JSONDecodeError:
        response_markdown = "*⚠️ An error occurred. Please try again.*"

    # Show assistant response and download (if available)
    with st.chat_message("assistant"):
        st.markdown(f"**Assistant:**\n{response_markdown}", unsafe_allow_html=True)

        if file_data:
            st.download_button(
                label="📄 Download API Response",
                data=file_data,
                file_name="api_response.json",
                mime="application/json",
                key=f"download_{len(st.session_state.chat_history)}"
            )

        if debug_data and SHOW_DEBUG_UI:
            debug_key = f"debug_{len(st.session_state.chat_history)}"
            show_debug = st.toggle("🛠️ Show Debug", key=debug_key)
            if show_debug:
                for k, v in debug_data.items():
                    st.code(f"{k}: {v}", language="json")


    # Save chat history
    st.session_state.chat_history.append({
        "user": user_input,
        "response": response_markdown,
        "debug": debug_data,
        "file_data": file_data,
    })
