import streamlit as st
from utils.data import get_session, search_patients, load_patient
from utils.translate import LANGUAGES, translate_many

st.set_page_config(page_title="Insaan", page_icon=":material/cardiology:", layout="wide")

session = get_session()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "patient_id" not in st.session_state:
    st.session_state.patient_id = None
if "patient_info" not in st.session_state:
    st.session_state.patient_info = None
if "lang" not in st.session_state:
    st.session_state.lang = "en"
if "lang_pref" not in st.session_state:
    st.session_state.lang_pref = "auto"


def _on_lang_pref_change():
    if st.session_state.lang_pref != "auto":
        st.session_state.lang = st.session_state.lang_pref

# --- Navigation ---
page = st.navigation(
    {
        "Patient": [
            st.Page("app_pages/patient_portal.py", title="Patient portal", icon=":material/dashboard:"),
            st.Page("app_pages/chat.py", title="Chat with Insaan", icon=":material/chat:"),
        ],
        "Admin": [
            st.Page("app_pages/admin_dashboard.py", title="Admin dashboard", icon=":material/admin_panel_settings:"),
        ],
    }
)

# --- Sidebar ---
with st.sidebar:
    st.title(":material/cardiology: Insaan")
    st.caption("The healthcare concierge")

    st.selectbox(
        ":material/translate: Language",
        options=["auto"] + list(LANGUAGES),
        format_func=lambda c: "Auto-detect" if c == "auto" else LANGUAGES[c],
        key="lang_pref",
        on_change=_on_lang_pref_change,
        help="Auto-detect replies in whatever language you write in.",
    )

    st.subheader(":material/person_search: Patient login")
    search = st.text_input("Search by name", placeholder="e.g. Charles Davis", label_visibility="collapsed")

    if search:
        patients = search_patients(session, search)
        if patients:
            for p in patients:
                label = f"{p['NAME']} (Age {p['AGE']}, {p['PRIMARY_INSURANCE']})"
                if st.button(label, key=f"pat_{p['PATIENT_ID']}"):
                    st.session_state.patient_id = p["PATIENT_ID"]
                    st.session_state.patient_info = load_patient(session, p["PATIENT_ID"])
                    st.session_state.messages = []
                    if st.session_state.lang_pref == "auto":
                        st.session_state.lang = "en"
                    st.rerun()
        else:
            st.caption("No patients found.")

    if st.session_state.patient_info:
        pi = st.session_state.patient_info
        with st.container(border=True):
            st.metric("Current patient", pi["full_name"])
            st.caption(
                f"ID: {pi['patient_id']} · {pi['age']}yo {pi['gender']} · {pi['insurance']}"
            )

title = page.title
if st.session_state.lang != "en" and page.title != "Admin dashboard":
    title = translate_many(session, [page.title], st.session_state.lang).get(page.title, page.title)
st.title(f"{page.icon} {title}")
page.run()
