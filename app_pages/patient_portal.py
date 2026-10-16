import streamlit as st
from utils.data import get_session, load_patient_summary

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

if nudges:
    with st.container(border=True):
        st.subheader(":material/notifications: Action items")
        for icon, text in nudges:
            st.markdown(f"{icon} {text}")

# --- KPI row ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    with st.container(border=True):
        st.metric("Age", f"{pi['age']} years")
with col2:
    with st.container(border=True):
        st.metric("Blood type", pi["blood_type"] or "N/A")
with col3:
    with st.container(border=True):
        st.metric("Insurance", pi["insurance"])
with col4:
    with st.container(border=True):
        st.metric("Status", pi["status"])

# --- Diagnoses ---
st.subheader(":material/medical_information: Diagnoses")
if summary["diagnoses"]:
    diag_data = [
        {
            "Date": str(d["DIAGNOSIS_DATE"]),
            "Condition": d["DIAGNOSIS_DESCRIPTION"],
            "Category": d["CATEGORY"],
            "Chronic": "Yes" if d["IS_CHRONIC"] else "No",
        }
        for d in summary["diagnoses"]
    ]
    st.dataframe(diag_data, use_container_width=True, hide_index=True)
else:
    st.caption("No diagnoses on record.")

# --- Medications + Billing side by side ---
col_med, col_bill = st.columns(2)
with col_med:
    st.subheader(":material/medication: Active medications")
    if summary["active_meds"]:
        med_data = [
            {
                "Medication": m["MEDICATION_NAME"],
                "Dosage": m["DOSAGE"],
                "Frequency": m["FREQUENCY"],
                "Cost": f"${m['COST']:.2f}" if m["COST"] else "N/A",
                "Refills": m["REFILLS_REMAINING"],
            }
            for m in summary["active_meds"]
        ]
        st.dataframe(med_data, use_container_width=True, hide_index=True)
    else:
        st.caption("No active medications.")

with col_bill:
    st.subheader(":material/payments: Yearly costs")
    if summary["billing"]:
        bill_data = [
            {
                "Year": int(b["YEAR"]),
                "Billed": f"${b['TOTAL_BILLED']:,.2f}",
                "Out of pocket": f"${b['OUT_OF_POCKET']:,.2f}",
                "Insurance paid": f"${b['INSURANCE_PAID']:,.2f}",
            }
            for b in summary["billing"]
        ]
        st.dataframe(bill_data, use_container_width=True, hide_index=True)
    else:
        st.caption("No billing records.")

# --- Recent visits ---
st.subheader(":material/event_note: Recent visits")
if summary["recent_visits"]:
    visit_data = [
        {
            "Date": str(v["ENCOUNTER_DATE"]),
            "Type": v["ENCOUNTER_TYPE"],
            "Complaint": v["CHIEF_COMPLAINT"] or "N/A",
            "Provider": v["PROVIDER_NAME"] or "N/A",
            "Specialty": v["SPECIALTY"] or "N/A",
            "Status": v["STATUS"],
        }
        for v in summary["recent_visits"]
    ]
    st.dataframe(visit_data, use_container_width=True, hide_index=True)
else:
    st.caption("No recent visits.")
