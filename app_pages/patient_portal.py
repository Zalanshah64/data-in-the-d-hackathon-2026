import streamlit as st
from utils.data import get_session, load_patient_summary
from utils.translate import LANGUAGES, translate_many

session = get_session()
pi = st.session_state.get("patient_info")

if not pi:
    st.title(":material/cardiology: Welcome to Insaan")
    st.markdown("**Your personal healthcare concierge.**")
    st.markdown("Search for a patient in the sidebar to get started.")
    st.info(
        "Try searching for **Charles Davis** — our demo patient with rich data "
        "across 7 condition categories.",
        icon=":material/person_search:",
    )
    st.stop()

summary = load_patient_summary(session, pi["patient_id"])
lang = st.session_state.get("lang", "en")

REQUEST_LABELS = {
    "CANCEL_APPOINTMENT": "Cancelled appointment",
    "RESCHEDULE_APPOINTMENT": "Rescheduled appointment",
    "UPDATE_INSURANCE": "Insurance update",
    "REFILL_REQUEST": "Refill request",
    "BOOK_APPOINTMENT": "Booked appointment",
}

# --- Nudges ---
nudges = []
if summary["upcoming"]:
    nudges.append(
        (":material/calendar_today:", f"You have **{len(summary['upcoming'])} upcoming appointment(s)**.")
    )
low_refill = [
    m for m in summary["active_meds"]
    if m["REFILLS_REMAINING"] is not None and m["REFILLS_REMAINING"] <= 1
]
if low_refill:
    nudges.append(
        (":material/medication:", f"**{len(low_refill)} medication(s)** are low on refills.")
    )
if summary["eligible_trials"] > 0:
    nudges.append(
        (":material/science:", f"**{summary['eligible_trials']} clinical trial(s)** recruiting in your condition areas.")
    )

# --- Translation: gather every English string on the page, translate in one call ---
STATIC = [
    "Action items", "Age", "years", "Blood type", "Insurance", "Status", "N/A",
    "Diagnoses", "Date", "Condition", "Category", "Chronic", "Yes", "No", "No diagnoses on record.",
    "Active medications", "Medication", "Dosage", "Frequency", "Cost", "Refills", "No active medications.",
    "Yearly costs", "Year", "Billed", "Out of pocket", "Insurance paid", "No billing records.",
    "Recent visits", "Type", "Complaint", "Provider", "Specialty", "No recent visits.",
    "My requests", "Request", "Details",
    "No requests yet. Ask Insaan in chat to cancel or reschedule a visit, "
    "update your insurance, or request a refill.",
    "Show in English",
]
dynamic = [text for _, text in nudges] + list(REQUEST_LABELS.values()) + [pi["status"]]
dynamic += [v for d in summary["diagnoses"] for v in (d["DIAGNOSIS_DESCRIPTION"], d["CATEGORY"])]
dynamic += [m["FREQUENCY"] for m in summary["active_meds"]]
dynamic += [
    v for e in summary["recent_visits"]
    for v in (e["ENCOUNTER_TYPE"], e["CHIEF_COMPLAINT"], e["SPECIALTY"], e["STATUS"])
]
dynamic += [v for r in summary["requests"] for v in (r["DETAILS"], r["STATUS"].title())]

if lang != "en":
    with st.spinner(f"Translating to {LANGUAGES.get(lang, lang)}..."):
        tr = translate_many(session, STATIC + dynamic, lang)
else:
    tr = {}


def t(text):
    return tr.get(text, text) if text else text


def _show_english():
    st.session_state.lang = "en"
    if st.session_state.get("lang_pref", "auto") != "auto":
        st.session_state.lang_pref = "en"


if lang != "en":
    c1, c2 = st.columns([4, 1])
    c1.caption(f":material/translate: {LANGUAGES.get(lang, lang)}")
    c2.button(t("Show in English"), icon=":material/language:", on_click=_show_english)

if nudges:
    with st.container(border=True):
        st.subheader(f":material/notifications: {t('Action items')}")
        for icon, text in nudges:
            st.markdown(f"{icon} {t(text)}")

# --- KPI row ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    with st.container(border=True):
        st.metric(t("Age"), f"{pi['age']} {t('years')}")
with col2:
    with st.container(border=True):
        st.metric(t("Blood type"), pi["blood_type"] or t("N/A"))
with col3:
    with st.container(border=True):
        st.metric(t("Insurance"), pi["insurance"])
with col4:
    with st.container(border=True):
        st.metric(t("Status"), t(pi["status"]))

# --- Diagnoses ---
st.subheader(f":material/medical_information: {t('Diagnoses')}")
if summary["diagnoses"]:
    diag_data = [
        {
            t("Date"): str(d["DIAGNOSIS_DATE"]),
            t("Condition"): t(d["DIAGNOSIS_DESCRIPTION"]),
            t("Category"): t(d["CATEGORY"]),
            t("Chronic"): t("Yes") if d["IS_CHRONIC"] else t("No"),
        }
        for d in summary["diagnoses"]
    ]
    st.dataframe(diag_data, use_container_width=True, hide_index=True)
else:
    st.caption(t("No diagnoses on record."))

# --- Medications + Billing side by side ---
col_med, col_bill = st.columns(2)
with col_med:
    st.subheader(f":material/medication: {t('Active medications')}")
    if summary["active_meds"]:
        med_data = [
            {
                t("Medication"): m["MEDICATION_NAME"],
                t("Dosage"): m["DOSAGE"],
                t("Frequency"): t(m["FREQUENCY"]),
                t("Cost"): f"${m['COST']:.2f}" if m["COST"] else t("N/A"),
                t("Refills"): m["REFILLS_REMAINING"],
            }
            for m in summary["active_meds"]
        ]
        st.dataframe(med_data, use_container_width=True, hide_index=True)
    else:
        st.caption(t("No active medications."))

with col_bill:
    st.subheader(f":material/payments: {t('Yearly costs')}")
    if summary["billing"]:
        bill_data = [
            {
                t("Year"): int(b["YEAR"]),
                t("Billed"): f"${b['TOTAL_BILLED']:,.2f}",
                t("Out of pocket"): f"${b['OUT_OF_POCKET']:,.2f}",
                t("Insurance paid"): f"${b['INSURANCE_PAID']:,.2f}",
            }
            for b in summary["billing"]
        ]
        st.dataframe(bill_data, use_container_width=True, hide_index=True)
    else:
        st.caption(t("No billing records."))

# --- Recent visits ---
st.subheader(f":material/event_note: {t('Recent visits')}")
if summary["recent_visits"]:
    visit_data = [
        {
            t("Date"): str(v["ENCOUNTER_DATE"]),
            t("Type"): t(v["ENCOUNTER_TYPE"]),
            t("Complaint"): t(v["CHIEF_COMPLAINT"]) or t("N/A"),
            t("Provider"): v["PROVIDER_NAME"] or t("N/A"),
            t("Specialty"): t(v["SPECIALTY"]) or t("N/A"),
            t("Status"): t(v["STATUS"]),
        }
        for v in summary["recent_visits"]
    ]
    st.dataframe(visit_data, use_container_width=True, hide_index=True)
else:
    st.caption(t("No recent visits."))

# --- Self-serve requests ---
st.subheader(f":material/task_alt: {t('My requests')}")
if summary["requests"]:
    request_data = [
        {
            t("Date"): r["CREATED_AT"].strftime("%Y-%m-%d %H:%M"),
            t("Request"): t(REQUEST_LABELS.get(r["REQUEST_TYPE"], r["REQUEST_TYPE"])),
            t("Details"): t(r["DETAILS"]),
            t("Status"): t(r["STATUS"].title()),
        }
        for r in summary["requests"]
    ]
    st.dataframe(request_data, use_container_width=True, hide_index=True)
else:
    st.caption(t(
        "No requests yet. Ask Insaan in chat to cancel or reschedule a visit, "
        "update your insurance, or request a refill."
    ))
