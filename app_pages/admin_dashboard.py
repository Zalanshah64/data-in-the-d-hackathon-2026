import altair as alt
import streamlit as st
from utils.data import get_session
from utils.analytics import NEGATIVE_THRESHOLD, load_messages, load_requests, score_conversations, summarize_dashboard
from utils.translate import LANGUAGES

# Assumption for the deflection estimate: an average inbound patient call.
AVG_CALL_MINUTES = 8

REQUEST_LABELS = {
    "CANCEL_APPOINTMENT": "Cancelled appointment",
    "RESCHEDULE_APPOINTMENT": "Rescheduled appointment",
    "UPDATE_INSURANCE": "Insurance update",
    "REFILL_REQUEST": "Refill request",
    "BOOK_APPOINTMENT": "Booked appointment",
}
SENTIMENT_COLORS = alt.Scale(
    domain=["positive", "neutral", "negative", "unscored"], range=["#2e7d32", "#90a4ae", "#c62828", "#cfd8dc"]
)

session = get_session()

# Reserved first so the AI summary sits at the very top, but is generated last so
# the charts render without waiting on the LLM.
summary_slot = st.container()

c1, c2 = st.columns([5, 1])
c1.caption(
    "Insurance company view. Every conversation Insaan resolves is a call your contact center never had to take."
)
if c2.button("Refresh", icon=":material/refresh:", use_container_width=True):
    with st.spinner("Scoring new conversations..."):
        score_conversations(session)
    load_messages.clear()
    load_requests.clear()

msgs = load_messages(session)
reqs = load_requests(session)

if msgs.empty:
    st.info("No patient conversations yet. Chat with Insaan as a patient to populate this dashboard.",
            icon=":material/forum:")
    st.stop()

msgs["LANGUAGE"] = msgs["LANGUAGE_CODE"].map(lambda c: LANGUAGES.get(c, c or "Unknown"))
scored = msgs[msgs["SENTIMENT_SCORE"].notna()]
sessions = msgs["SESSION_ID"].nunique()
completed_actions = int((reqs["STATUS"].str.upper() != "FAILED").sum()) if not reqs.empty else 0

# --- KPI row ---
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    with st.container(border=True):
        st.metric("Conversations", f"{sessions:,}", help="Distinct chat sessions.")
with k2:
    with st.container(border=True):
        st.metric("Patients served", f"{msgs['PATIENT_ID'].nunique():,}")
with k3:
    with st.container(border=True):
        st.metric("Self-serve actions", f"{completed_actions:,}",
                  help="Appointments, insurance changes and refills completed without staff.")
with k4:
    with st.container(border=True):
        st.metric("Est. agent hours saved", f"{sessions * AVG_CALL_MINUTES / 60:,.1f}",
                  help=f"Conversations × {AVG_CALL_MINUTES} min average call. An estimate, not a measurement.")
with k5:
    with st.container(border=True):
        avg = scored["SENTIMENT_SCORE"].mean() if not scored.empty else None
        st.metric("Avg sentiment", f"{avg:+.2f}" if avg is not None else "N/A",
                  help="AI_SENTIMENT on each patient message: +1 positive, 0 neutral/mixed, -1 negative.")

# --- Volume + sentiment trend ---
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader(":material/forum: Patient volume")
        volume = msgs.groupby("DAY").agg(
            Conversations=("SESSION_ID", "nunique"), Messages=("CONVERSATION_ID", "count")
        ).reset_index()
        st.altair_chart(
            alt.Chart(volume).mark_bar(color="#1565c0", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("DAY:T", title=None),
                y=alt.Y("Conversations:Q", title="Conversations"),
                tooltip=["DAY:T", "Conversations:Q", "Messages:Q"],
            ).properties(height=260),
            use_container_width=True,
        )
with right:
    with st.container(border=True):
        st.subheader(":material/sentiment_satisfied: Sentiment trend")
        if scored.empty:
            st.caption("No scored messages yet.")
        else:
            trend = scored.groupby("DAY").agg(
                Sentiment=("SENTIMENT_SCORE", "mean"), Messages=("CONVERSATION_ID", "count")
            ).reset_index()
            base = alt.Chart(trend).encode(x=alt.X("DAY:T", title=None))
            line = base.mark_line(point=True, color="#1565c0").encode(
                y=alt.Y("Sentiment:Q", scale=alt.Scale(domain=[-1, 1]), title="Avg sentiment"),
                tooltip=["DAY:T", alt.Tooltip("Sentiment:Q", format="+.2f"), "Messages:Q"],
            )
            zero = base.mark_rule(strokeDash=[4, 4], color="#90a4ae").encode(y=alt.datum(0))
            st.altair_chart((line + zero).properties(height=260), use_container_width=True)

# --- Topics + languages ---
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader(":material/topic: What patients ask about")
        topics = msgs.groupby(["TOPIC", "SENTIMENT_LABEL"]).size().reset_index(name="Messages")
        st.altair_chart(
            alt.Chart(topics).mark_bar().encode(
                y=alt.Y("TOPIC:N", sort="-x", title=None),
                x=alt.X("sum(Messages):Q", title="Messages"),
                color=alt.Color("SENTIMENT_LABEL:N", scale=SENTIMENT_COLORS, title="Sentiment"),
                tooltip=["TOPIC:N", "SENTIMENT_LABEL:N", "Messages:Q"],
            ).properties(height=260),
            use_container_width=True,
        )
with right:
    with st.container(border=True):
        st.subheader(":material/translate: Languages served")
        langs = msgs.groupby("LANGUAGE")["SESSION_ID"].nunique().reset_index(name="Conversations")
        st.altair_chart(
            alt.Chart(langs).mark_arc(innerRadius=60).encode(
                theta="Conversations:Q",
                color=alt.Color("LANGUAGE:N", title="Language"),
                tooltip=["LANGUAGE:N", "Conversations:Q"],
            ).properties(height=260),
            use_container_width=True,
        )

# --- Self-serve deflection ---
with st.container(border=True):
    st.subheader(":material/task_alt: Requests handled without a call")
    if reqs.empty:
        st.caption("No self-serve actions yet.")
    else:
        reqs["Request"] = reqs["REQUEST_TYPE"].map(lambda r: REQUEST_LABELS.get(r, r.replace("_", " ").title()))
        counts = reqs.groupby("Request").size().reset_index(name="Count")
        bar_col, list_col = st.columns([1, 1])
        with bar_col:
            st.altair_chart(
                alt.Chart(counts).mark_bar(color="#2e7d32").encode(
                    y=alt.Y("Request:N", sort="-x", title=None),
                    x=alt.X("Count:Q", title="Requests", axis=alt.Axis(tickMinStep=1)),
                    tooltip=["Request:N", "Count:Q"],
                ).properties(height=220),
                use_container_width=True,
            )
        with list_col:
            st.dataframe(
                reqs.sort_values("CREATED_AT", ascending=False)[["CREATED_AT", "PATIENT_NAME", "Request", "DETAILS"]],
                hide_index=True,
                use_container_width=True,
                height=220,
                column_config={
                    "CREATED_AT": st.column_config.DatetimeColumn("When", format="MMM D, h:mm a"),
                    "PATIENT_NAME": "Patient",
                    "DETAILS": "Details",
                },
            )

# --- Alerts + common questions ---
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader(":material/warning: Negative sentiment alerts")
        alerts = scored[scored["SENTIMENT_SCORE"] < NEGATIVE_THRESHOLD].sort_values("CREATED_AT", ascending=False)
        if alerts.empty:
            st.caption("No frustrated patients. Nice.")
        else:
            st.caption(f"{len(alerts)} message(s) worth a follow-up from a care coordinator.")
            st.dataframe(
                alerts[["CREATED_AT", "PATIENT_NAME", "TOPIC", "ORIGINAL_MESSAGE", "MESSAGE"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "CREATED_AT": st.column_config.DatetimeColumn("When", format="MMM D, h:mm a"),
                    "PATIENT_NAME": "Patient",
                    "TOPIC": "Topic",
                    "ORIGINAL_MESSAGE": "Message",
                    "MESSAGE": "English",
                },
            )
with right:
    with st.container(border=True):
        st.subheader(":material/format_list_numbered: Most common questions")
        questions = msgs.assign(Q=msgs["MESSAGE"].str.strip().str.rstrip("?.! ").str.lower())
        top = (
            questions.groupby("Q")
            .agg(Question=("MESSAGE", "first"), Topic=("TOPIC", "first"), Asked=("CONVERSATION_ID", "count"))
            .sort_values("Asked", ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        st.dataframe(top, hide_index=True, use_container_width=True)

# --- AI summary (rendered into the slot at the top) ---
topic_counts = msgs["TOPIC"].value_counts().to_dict()
sentiment_counts = msgs["SENTIMENT_LABEL"].value_counts().to_dict()
lang_counts = langs.set_index("LANGUAGE")["Conversations"].to_dict()
request_counts = (
    reqs["REQUEST_TYPE"].map(lambda r: REQUEST_LABELS.get(r, r)).value_counts().to_dict() if not reqs.empty else {}
)
negative_lines = "\n".join(
    f"- [{r.TOPIC}] {r.MESSAGE}" for r in alerts.head(8).itertuples()
) or "- none"
avg_line = f"{avg:+.2f}" if avg is not None else "not scored"
digest = (
    f"Date range: {msgs['DAY'].min():%Y-%m-%d} to {msgs['DAY'].max():%Y-%m-%d}\n"
    f"Conversations: {sessions}; patient messages: {len(msgs)}; patients: {msgs['PATIENT_ID'].nunique()}\n"
    f"Average sentiment (-1 to 1): {avg_line}\n"
)
digest += (
    f"Sentiment counts: {sentiment_counts}\n"
    f"Topic counts: {topic_counts}\n"
    f"Conversations by language: {lang_counts}\n"
    f"Self-serve actions completed without staff: {completed_actions} {request_counts}\n"
    f"Estimated agent hours saved: {sessions * AVG_CALL_MINUTES / 60:.1f} (assumes {AVG_CALL_MINUTES} min per call)\n"
    f"Negative patient messages (English):\n{negative_lines}"
)

with summary_slot:
    with st.container(border=True):
        st.subheader(":material/auto_awesome: AI summary")
        with st.spinner("Summarizing today's patient conversations..."):
            try:
                summary = summarize_dashboard(session, digest)
            except Exception:
                summary = None
        if summary:
            st.markdown(summary.replace("$", "\\$"))
            st.caption("Generated with AI_COMPLETE from the data on this page.")
        else:
            st.caption("Summary unavailable right now. The charts below are up to date.")
