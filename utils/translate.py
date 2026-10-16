import json
import streamlit as st

LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "tr": "Turkish",
    "hr": "Croatian",
    "cs": "Czech",
    "fi": "Finnish",
    "el": "Greek",
    "he": "Hebrew",
    "no": "Norwegian",
    "ro": "Romanian",
    "sv": "Swedish",
}

_LABELS_SQL = ", ".join(f"'{code}'" for code in LANGUAGES)


def detect_and_translate(session, text):
    """Return (language_code, english_text). AI_TRANSLATE auto-detects the source ('');
    AI_CLASSIFY names the language so we can reply in kind."""
    row = session.sql(
        f"""
        SELECT
            AI_CLASSIFY(
                ?,
                [{_LABELS_SQL}],
                {{'task_description': 'Identify the ISO 639-1 language code the text is written in'}}
            ):labels[0]::STRING AS LANG,
            AI_TRANSLATE(?, '', 'en') AS EN
        """,
        params=[text, text],
    ).collect()[0]
    lang = row["LANG"] if row["LANG"] in LANGUAGES else "en"
    if lang == "en":
        return "en", text
    return lang, row["EN"] or text


def translate_from_english(session, text, lang):
    if lang == "en" or not text:
        return text
    row = session.sql(
        "SELECT AI_TRANSLATE(?, 'en', ?) AS T", params=[text, lang]
    ).collect()[0]
    return row["T"] or text


@st.cache_data(show_spinner=False, ttl=3600)
def _translate_batch(_session, texts, lang):
    rows = _session.sql(
        """
        SELECT f.index AS I, AI_TRANSLATE(f.value::STRING, 'en', ?) AS T
        FROM TABLE(FLATTEN(INPUT => PARSE_JSON(?))) f
        """,
        params=[lang, json.dumps(list(texts))],
    ).collect()
    out = dict(zip(texts, texts))
    for r in rows:
        if r["T"]:
            out[texts[r["I"]]] = r["T"]
    return out


def translate_many(session, texts, lang):
    """Translate a set of English UI strings in one cached AI_TRANSLATE call. Returns {english: translated}."""
    unique = tuple(sorted({t for t in texts if t}))
    if lang == "en" or not unique:
        return {t: t for t in unique}
    return _translate_batch(session, unique, lang)


def log_message(session, session_id, patient_id, role, message_en, lang, original):
    session.sql(
        """
        INSERT INTO HEALTHCARE_DW.INSAAN.CONVERSATIONS
            (SESSION_ID, PATIENT_ID, ROLE, MESSAGE, LANGUAGE_CODE, ORIGINAL_MESSAGE)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        params=[session_id, patient_id, role, message_en, lang, original],
    ).collect()
