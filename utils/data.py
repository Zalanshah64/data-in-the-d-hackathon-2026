import streamlit as st
from snowflake.snowpark.context import get_active_session


@st.cache_resource
def get_session():
    return get_active_session()


def search_patients(session, search_term):
    return session.sql(
        """
        SELECT PATIENT_ID, FIRST_NAME || ' ' || LAST_NAME AS NAME,
               PRIMARY_INSURANCE, DATEDIFF('year', DATE_OF_BIRTH, CURRENT_DATE()) AS AGE
        FROM HEALTHCARE_DW.CORE.PATIENTS
        WHERE LOWER(FIRST_NAME || ' ' || LAST_NAME) LIKE '%' || LOWER(?) || '%'
        LIMIT 10
        """,
        params=[search_term],
    ).collect()


def load_patient(session, patient_id):
    info = session.sql(
        """
        SELECT p.PATIENT_ID, p.FIRST_NAME, p.LAST_NAME, p.DATE_OF_BIRTH, p.GENDER,
               p.PRIMARY_INSURANCE, p.BLOOD_TYPE, p.STATE_CODE, p.HAS_CHRONIC_CONDITION, p.STATUS,
               DATEDIFF('year', p.DATE_OF_BIRTH, CURRENT_DATE()) AS AGE
        FROM HEALTHCARE_DW.CORE.PATIENTS p
        WHERE p.PATIENT_ID = ?
        """,
        params=[patient_id],
    ).collect()
    if not info:
        return None
    row = info[0]
    return {
        "patient_id": row["PATIENT_ID"],
        "first_name": row["FIRST_NAME"],
        "last_name": row["LAST_NAME"],
        "full_name": f"{row['FIRST_NAME']} {row['LAST_NAME']}",
        "dob": str(row["DATE_OF_BIRTH"]),
        "age": row["AGE"],
        "gender": row["GENDER"],
        "insurance": row["PRIMARY_INSURANCE"],
        "blood_type": row["BLOOD_TYPE"],
        "state": row["STATE_CODE"],
        "chronic": row["HAS_CHRONIC_CONDITION"],
        "status": row["STATUS"],
    }


def load_patient_summary(session, patient_id):
    diagnoses = session.sql(
        """
        SELECT DIAGNOSIS_DESCRIPTION, CATEGORY, IS_CHRONIC, DIAGNOSIS_DATE
        FROM HEALTHCARE_DW.CLINICAL.DIAGNOSES
        WHERE PATIENT_ID = ?
        ORDER BY DIAGNOSIS_DATE DESC
        """,
        params=[patient_id],
    ).collect()

    active_meds = session.sql(
        """
        SELECT MEDICATION_NAME, DOSAGE, FREQUENCY, COST, REFILLS_REMAINING
        FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS
        WHERE PATIENT_ID = ? AND STATUS = 'FILLED'
        ORDER BY PRESCRIBED_DATE DESC
        """,
        params=[patient_id],
    ).collect()

    recent_visits = session.sql(
        """
        SELECT e.ENCOUNTER_DATE, e.ENCOUNTER_TYPE, e.CHIEF_COMPLAINT, e.STATUS,
               p.FIRST_NAME || ' ' || p.LAST_NAME AS PROVIDER_NAME, p.SPECIALTY
        FROM HEALTHCARE_DW.CLINICAL.ENCOUNTERS e
        LEFT JOIN HEALTHCARE_DW.CORE.PROVIDERS p ON e.PROVIDER_ID = p.PROVIDER_ID
        WHERE e.PATIENT_ID = ?
        ORDER BY e.ENCOUNTER_DATE DESC
        LIMIT 8
        """,
        params=[patient_id],
    ).collect()

    billing = session.sql(
        """
        SELECT YEAR(c.SERVICE_DATE) AS YEAR,
               SUM(c.BILLED_AMOUNT) AS TOTAL_BILLED,
               SUM(py.PATIENT_RESPONSIBILITY) AS OUT_OF_POCKET,
               SUM(py.INSURANCE_PAID) AS INSURANCE_PAID
        FROM HEALTHCARE_DW.BILLING.CLAIMS c
        JOIN HEALTHCARE_DW.BILLING.PAYMENTS py ON c.CLAIM_ID = py.CLAIM_ID
        WHERE c.PATIENT_ID = ?
        GROUP BY YEAR(c.SERVICE_DATE)
        ORDER BY YEAR DESC
        """,
        params=[patient_id],
    ).collect()

    upcoming = session.sql(
        """
        SELECT ENCOUNTER_DATE, ENCOUNTER_TYPE, CHIEF_COMPLAINT
        FROM HEALTHCARE_DW.CLINICAL.ENCOUNTERS
        WHERE PATIENT_ID = ? AND STATUS = 'SCHEDULED'
        ORDER BY ENCOUNTER_DATE
        """,
        params=[patient_id],
    ).collect()

    eligible_trials = session.sql(
        """
        SELECT COUNT(*) AS CNT
        FROM HEALTHCARE_DW.RESEARCH.CLINICAL_TRIALS
        WHERE STATUS = 'RECRUITING'
          AND THERAPEUTIC_AREA IN (
            SELECT DISTINCT CASE
              WHEN d.CATEGORY = 'Cardiovascular' THEN 'Cardiology'
              WHEN d.CATEGORY = 'Endocrine' THEN 'Endocrinology'
              WHEN d.CATEGORY = 'Metabolic' THEN 'Endocrinology'
              WHEN d.CATEGORY = 'Neurological' THEN 'Neurology'
              WHEN d.CATEGORY = 'Mental Health' THEN 'Psychiatry'
              ELSE d.CATEGORY
            END
            FROM HEALTHCARE_DW.CLINICAL.DIAGNOSES d
            WHERE d.PATIENT_ID = ?
          )
        """,
        params=[patient_id],
    ).collect()

    return {
        "diagnoses": diagnoses,
        "active_meds": active_meds,
        "recent_visits": recent_visits,
        "billing": billing,
        "upcoming": upcoming,
        "eligible_trials": eligible_trials[0]["CNT"] if eligible_trials else 0,
    }
