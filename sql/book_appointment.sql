-- Book a new visit with a doctor the patient has already seen.
-- Exposed to INSAAN_AGENT as GetPastProviders (read) and BookAppointment (write).

USE SCHEMA HEALTHCARE_DW.INSAAN;

CREATE OR REPLACE PROCEDURE GET_PAST_PROVIDERS(P_PATIENT_ID NUMBER)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
  result VARCHAR;
BEGIN
  SELECT COALESCE(ARRAY_AGG(OBJECT_CONSTRUCT(
           'provider_id', PROVIDER_ID,
           'name', NAME,
           'specialty', SPECIALTY,
           'primary_care', SPECIALTY IN ('Family Medicine', 'Internal Medicine', 'Pediatrics'),
           'visits', VISITS,
           'last_visit', LAST_VISIT::VARCHAR))
           WITHIN GROUP (ORDER BY LAST_VISIT DESC), ARRAY_CONSTRUCT())::VARCHAR
    INTO :result
    FROM (
      SELECT pr.PROVIDER_ID, pr.FIRST_NAME || ' ' || pr.LAST_NAME AS NAME, pr.SPECIALTY,
             COUNT(*) AS VISITS, MAX(e.ENCOUNTER_DATE) AS LAST_VISIT
        FROM HEALTHCARE_DW.CLINICAL.ENCOUNTERS e
        JOIN HEALTHCARE_DW.CORE.PROVIDERS pr ON e.PROVIDER_ID = pr.PROVIDER_ID
       WHERE e.PATIENT_ID = :P_PATIENT_ID
         AND e.STATUS = 'COMPLETED'
         AND pr.SPECIALTY <> 'Emergency Medicine'
       GROUP BY ALL
    );
  RETURN result;
END;
$$;

CREATE OR REPLACE PROCEDURE BOOK_APPOINTMENT(
  P_PATIENT_ID NUMBER, P_PROVIDER_ID NUMBER, P_DATE VARCHAR, P_VISIT_TYPE VARCHAR, P_REASON VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
  appt_date DATE;
  visit_type VARCHAR;
  reason VARCHAR;
  doc_name VARCHAR;
  doc_specialty VARCHAR;
  facility VARCHAR;
  dup_count NUMBER;
  new_id NUMBER;
  details VARCHAR;
BEGIN
  appt_date := TRY_TO_DATE(:P_DATE);
  IF (appt_date IS NULL) THEN
    RETURN 'FAILED: could not read the date "' || P_DATE || '". Use YYYY-MM-DD.';
  END IF;
  IF (appt_date <= CURRENT_DATE()) THEN
    RETURN 'FAILED: the appointment date must be after today.';
  END IF;
  IF (appt_date > DATEADD('year', 1, CURRENT_DATE())) THEN
    RETURN 'FAILED: appointments can only be booked up to one year ahead.';
  END IF;

  visit_type := UPPER(TRIM(COALESCE(:P_VISIT_TYPE, 'OFFICE_VISIT')));
  IF (visit_type NOT IN ('OFFICE_VISIT', 'TELEHEALTH')) THEN
    visit_type := 'OFFICE_VISIT';
  END IF;
  reason := LEFT(TRIM(COALESCE(:P_REASON, 'Follow-up visit')), 200);

  -- Only doctors this patient has actually seen (no emergency physicians).
  SELECT MAX(pr.FIRST_NAME || ' ' || pr.LAST_NAME), MAX(pr.SPECIALTY),
         MAX_BY(e.FACILITY_ORG_ID, e.ENCOUNTER_DATE)
    INTO :doc_name, :doc_specialty, :facility
    FROM HEALTHCARE_DW.CLINICAL.ENCOUNTERS e
    JOIN HEALTHCARE_DW.CORE.PROVIDERS pr ON e.PROVIDER_ID = pr.PROVIDER_ID
   WHERE e.PATIENT_ID = :P_PATIENT_ID AND e.PROVIDER_ID = :P_PROVIDER_ID
     AND e.STATUS = 'COMPLETED' AND pr.SPECIALTY <> 'Emergency Medicine';
  IF (doc_name IS NULL) THEN
    RETURN 'FAILED: provider ' || P_PROVIDER_ID || ' is not one of this patient''s past doctors. Use GetPastProviders.';
  END IF;

  SELECT COUNT(*) INTO :dup_count
    FROM HEALTHCARE_DW.CLINICAL.ENCOUNTERS
   WHERE PATIENT_ID = :P_PATIENT_ID AND PROVIDER_ID = :P_PROVIDER_ID
     AND ENCOUNTER_DATE = :appt_date AND STATUS = 'SCHEDULED';
  IF (dup_count > 0) THEN
    RETURN 'FAILED: there is already an appointment with ' || doc_name || ' on ' || appt_date::VARCHAR || '.';
  END IF;

  SELECT COALESCE(MAX(ENCOUNTER_ID), 0) + 1 INTO :new_id FROM HEALTHCARE_DW.CLINICAL.ENCOUNTERS;
  details := 'Booked ' || LOWER(REPLACE(visit_type, '_', ' ')) || ' with ' || doc_name || ' (' || doc_specialty ||
             ') on ' || appt_date::VARCHAR || ' (encounter ' || new_id || ')';

  BEGIN TRANSACTION;
  INSERT INTO HEALTHCARE_DW.CLINICAL.ENCOUNTERS
    (ENCOUNTER_ID, PATIENT_ID, PROVIDER_ID, FACILITY_ORG_ID, ENCOUNTER_DATE, ENCOUNTER_TYPE, STATUS, CHIEF_COMPLAINT)
  VALUES (:new_id, :P_PATIENT_ID, :P_PROVIDER_ID, :facility, :appt_date, :visit_type, 'SCHEDULED', :reason);

  INSERT INTO HEALTHCARE_DW.INSAAN.SELF_SERVE_REQUESTS (PATIENT_ID, REQUEST_TYPE, DETAILS, STATUS)
  VALUES (:P_PATIENT_ID, 'BOOK_APPOINTMENT', :details, 'COMPLETED');
  COMMIT;

  RETURN 'SUCCESS: booked ' || LOWER(REPLACE(visit_type, '_', ' ')) || ' with ' || doc_name ||
         ' (' || doc_specialty || ') on ' || appt_date::VARCHAR || '.';
END;
$$;
