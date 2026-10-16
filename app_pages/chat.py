import streamlit as st
from utils.data import get_session
from utils.agent import call_agent


def _escape_dollars(text):
    """Escape bare $ signs so Streamlit doesn't treat them as LaTeX delimiters."""
    return text.replace("$", "\\$")


session = get_session()
pi = st.session_state.get("patient_info")

if not pi:
    st.info("Select a patient in the sidebar to start chatting.", icon=":material/person_search:")
    st.stop()

st.caption("Ask me anything about your health, medications, costs, or appointments.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(_escape_dollars(msg["content"]))

if prompt := st.chat_input("Ask Insaan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(_escape_dollars(prompt))

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = call_agent(session, prompt, pi, st.session_state.messages)
        st.markdown(_escape_dollars(response))
    st.session_state.messages.append({"role": "assistant", "content": response})
