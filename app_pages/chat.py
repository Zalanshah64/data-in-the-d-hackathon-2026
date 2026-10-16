import re
import time
import uuid
import streamlit as st
from utils.data import get_session, load_patient
from utils.agent import call_agent
from utils.analytics import score_conversations
from utils.translate import LANGUAGES, detect_and_translate, translate_from_english, log_message


def _escape_dollars(text):
    """Escape bare $ signs so Streamlit doesn't treat them as LaTeX delimiters."""
    return text.replace("$", "\\$")


def _stream_words(text, delay=0.015):
    """Yield the reply a word at a time for st.write_stream. Space-less scripts (CJK)
    come back as one long run, so those are cut into small character chunks."""
    for token in re.findall(r"\S+\s*|\s+", text):
        pieces = [token[i:i + 3] for i in range(0, len(token), 3)] if len(token) > 24 else [token]
        for piece in pieces:
            yield piece
            time.sleep(delay)


def _show_actions(actions):
    for action in actions:
        st.markdown(f":green[:material/check_circle: **{action}**]")


def _show_language(lang):
    if lang and lang != "en":
        st.caption(f":material/translate: {LANGUAGES.get(lang, lang)}")


session = get_session()
pi = st.session_state.get("patient_info")

if not pi:
    st.info("Select a patient in the sidebar to start chatting.", icon=":material/person_search:")
    st.stop()

if "chat_session_id" not in st.session_state:
    st.session_state.chat_session_id = str(uuid.uuid4())

st.caption(
    "Ask me anything about your health, medications, costs, or appointments — in any language. "
    "I can also cancel or reschedule visits, update your insurance, and request refills."
)

def _render_body(slot, msg):
    # Every bubble holds exactly one placeholder, so live and replayed messages share
    # the same element layout and Streamlit doesn't leave stale labels behind.
    with slot.container():
        st.markdown(_escape_dollars(msg["content"]))
        _show_actions(msg.get("actions", []))
        _show_language(msg.get("lang"))


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        _render_body(st.empty(), msg)

if prompt := st.chat_input("Ask Insaan..."):
    with st.chat_message("user"):
        slot = st.empty()
        with slot.container():
            st.markdown(_escape_dollars(prompt))
            with st.spinner("Understanding..."):
                detected, prompt_en = detect_and_translate(session, prompt)
        user_msg = {"role": "user", "content": prompt, "content_en": prompt_en, "lang": detected}
        _render_body(slot, user_msg)
    pref = st.session_state.get("lang_pref", "auto")
    lang = detected if pref == "auto" else pref
    st.session_state.lang = lang
    st.session_state.messages.append(user_msg)
    log_message(session, st.session_state.chat_session_id, pi["patient_id"], "user", prompt_en, detected, prompt)

    with st.chat_message("assistant"):
        slot = st.empty()
        with slot.container():
            with st.spinner("Thinking..."):
                response_en, actions = call_agent(session, prompt_en, pi, st.session_state.messages)
                response = translate_from_english(session, response_en, lang)
        bot_msg = {"role": "assistant", "content": response, "content_en": response_en, "actions": actions, "lang": lang}
        with slot.container():
            st.write_stream(_stream_words(_escape_dollars(response)))
        _render_body(slot, bot_msg)
    st.session_state.messages.append(bot_msg)
    log_message(session, st.session_state.chat_session_id, pi["patient_id"], "assistant", response_en, lang, response)
    # Tag topic + sentiment after the reply is on screen so the patient never waits on it.
    score_conversations(session)

    if actions:
        # Refresh patient record so the sidebar and portal reflect the change.
        st.session_state.patient_info = load_patient(session, pi["patient_id"])
        st.rerun()
