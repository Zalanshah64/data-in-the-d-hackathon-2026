import pandas as pd
import streamlit as st

NEGATIVE_THRESHOLD = 0  # scores below this are flagged


def score_conversations(session):
    """Tag topic + sentiment on any unscored patient messages (Stage 6 pipeline)."""
    try:
        session.sql("CALL HEALTHCARE_DW.INSAAN.SCORE_CONVERSATIONS()").collect()
    except Exception:
        # Scoring is analytics-only; never break the patient's chat over it.
        pass


def _with_day(df):
    # Bucket in pandas so Altair gets real datetimes rather than python date objects.
    if not df.empty:
        df["CREATED_AT"] = pd.to_datetime(df["CREATED_AT"])
        df["DAY"] = df["CREATED_AT"].dt.normalize()
    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_messages(_session):
    df = _session.sql(
        """
        SELECT CONVERSATION_ID, SESSION_ID, PATIENT_ID, PATIENT_NAME, MESSAGE, ORIGINAL_MESSAGE,
               LANGUAGE_CODE, COALESCE(TOPIC, 'unscored') AS TOPIC, SENTIMENT_SCORE,
               COALESCE(SENTIMENT_LABEL, 'unscored') AS SENTIMENT_LABEL, CREATED_AT
        FROM HEALTHCARE_DW.INSAAN.CONVERSATION_ANALYTICS
        ORDER BY CREATED_AT
        """
    ).to_pandas()
    return _with_day(df)


_SUMMARY_PROMPT = """You are briefing the operations lead at a health insurance company about their
AI patient concierge, Insaan, which handles patient questions that would otherwise be phone calls.

Using ONLY the data below, write a short executive summary in Markdown:
- Start directly with one bold headline sentence on the overall health of patient conversations.
  No title or headings.
- Then 3 to 5 "-" bullets: what patients ask about most, how they feel, which languages, and how
  much work was handled without staff. Quote numbers exactly as given; do not compute new ratios.
- End with one line starting "**Recommended action:**", grounded in the negative messages if any.
Do not invent numbers, patients or trends that are not in the data. Keep it under 150 words.
Do not use dollar signs.

DATA:
{digest}"""


@st.cache_data(ttl=600, show_spinner=False)
def summarize_dashboard(_session, digest):
    """AI_COMPLETE executive summary; cached per digest so it only regenerates when data changes."""
    row = _session.sql(
        "SELECT AI_COMPLETE('claude-sonnet-4-5', ?) AS S",
        params=[_SUMMARY_PROMPT.format(digest=digest)],
    ).collect()[0]
    return row["S"]


@st.cache_data(ttl=60, show_spinner=False)
def load_requests(_session):
    df = _session.sql(
        """
        SELECT r.REQUEST_ID, r.PATIENT_ID, p.FIRST_NAME || ' ' || p.LAST_NAME AS PATIENT_NAME,
               r.REQUEST_TYPE, r.DETAILS, r.STATUS, r.CREATED_AT
        FROM HEALTHCARE_DW.INSAAN.SELF_SERVE_REQUESTS r
        LEFT JOIN HEALTHCARE_DW.CORE.PATIENTS p ON p.PATIENT_ID = r.PATIENT_ID
        ORDER BY r.CREATED_AT
        """
    ).to_pandas()
    return _with_day(df)
