import streamlit as st
from utils.data import get_session, load_patient
from utils.agent import call_agent


def _escape_dollars(text):
    """Escape bare $ signs so Streamlit doesn't treat them as LaTeX delimiters."""
    return text.replace("$", "\\$")


def _show_actions(actions):
    for action in actions:
        st.markdown(f":green[:material/check_circle: **{action}**]")


session = get_session()
pi = st.session_state.get("patient_info")

if not pi:
    st.info("Select a patient in the sidebar to start chatting.", icon=":material/person_search:")
    st.stop()

st.caption(
    "Ask me anything about your health, medications, costs, or appointments. "
    "I can also cancel or reschedule visits, update your insurance, and request refills."
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(_escape_dollars(msg["content"]))
        _show_actions(msg.get("actions", []))

if prompt := st.chat_input("Ask Insaan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(_escape_dollars(prompt))

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response, actions = call_agent(session, prompt, pi, st.session_state.messages)
        st.markdown(_escape_dollars(response))
        _show_actions(actions)
    st.session_state.messages.append({"role": "assistant", "content": response, "actions": actions})

    if actions:
        # Refresh patient record so the sidebar and portal reflect the change.
        st.session_state.patient_info = load_patient(session, pi["patient_id"])
        st.rerun()
