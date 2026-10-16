-- Stage 6: Sentiment + topic tagging for patient messages.
-- Scores every patient message that has not been scored yet, so it both handles new
-- messages (called from the chat page) and backfills history.

USE SCHEMA HEALTHCARE_DW.INSAAN;

CREATE OR REPLACE PROCEDURE HEALTHCARE_DW.INSAAN.SCORE_CONVERSATIONS()
RETURNS NUMBER
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    scored NUMBER DEFAULT 0;
BEGIN
    -- Classify on the English text: AI_SENTIMENT doesn't cover every language we accept
    -- (e.g. Arabic), and the translated text keeps labels consistent across languages.
    CREATE OR REPLACE TEMPORARY TABLE HEALTHCARE_DW.INSAAN._PENDING_SCORES AS
    SELECT
        c.CONVERSATION_ID,
        c.PATIENT_ID,
        c.MESSAGE,
        AI_CLASSIFY(
            c.MESSAGE,
            [
                {'label': 'billing', 'description': 'bills, costs, claims, payments, insurance coverage'},
                {'label': 'clinical', 'description': 'symptoms, diagnoses, visits, lab results, clinical notes'},
                {'label': 'medication', 'description': 'prescriptions, refills, dosages, side effects'},
                {'label': 'scheduling', 'description': 'booking, cancelling or rescheduling appointments'},
                {'label': 'trials', 'description': 'clinical trials and research eligibility'},
                {'label': 'complaint', 'description': 'frustration, delays, poor service, grievances'},
                {'label': 'general', 'description': 'greetings, account questions, anything else'}
            ],
            {'task_description': 'Classify the topic of a patient message to their healthcare concierge'}
        ):labels[0]::STRING AS TOPIC,
        AI_SENTIMENT(c.MESSAGE):categories[0]:sentiment::STRING AS SENTIMENT_LABEL
    FROM HEALTHCARE_DW.INSAAN.CONVERSATIONS c
    LEFT JOIN HEALTHCARE_DW.INSAAN.CONVERSATION_SENTIMENT s
        ON s.CONVERSATION_ID = c.CONVERSATION_ID
    WHERE c.ROLE = 'user'
      AND s.CONVERSATION_ID IS NULL
      AND c.MESSAGE IS NOT NULL;

    INSERT INTO HEALTHCARE_DW.INSAAN.CONVERSATION_SENTIMENT
        (CONVERSATION_ID, PATIENT_ID, SENTIMENT_SCORE, MESSAGE, TOPIC)
    SELECT
        CONVERSATION_ID,
        PATIENT_ID,
        CASE SENTIMENT_LABEL
            WHEN 'positive' THEN 1
            WHEN 'negative' THEN -1
            ELSE 0  -- neutral, mixed, unknown
        END,
        MESSAGE,
        TOPIC
    FROM HEALTHCARE_DW.INSAAN._PENDING_SCORES;
    scored := SQLROWCOUNT;

    UPDATE HEALTHCARE_DW.INSAAN.CONVERSATIONS c
    SET TOPIC = p.TOPIC
    FROM HEALTHCARE_DW.INSAAN._PENDING_SCORES p
    WHERE c.CONVERSATION_ID = p.CONVERSATION_ID;

    DROP TABLE IF EXISTS HEALTHCARE_DW.INSAAN._PENDING_SCORES;
    RETURN :scored;
END;
$$;

-- One row per patient message with its sentiment, for the admin dashboard.
CREATE OR REPLACE VIEW HEALTHCARE_DW.INSAAN.CONVERSATION_ANALYTICS AS
SELECT
    c.CONVERSATION_ID,
    c.SESSION_ID,
    c.PATIENT_ID,
    p.FIRST_NAME || ' ' || p.LAST_NAME AS PATIENT_NAME,
    c.MESSAGE,
    c.ORIGINAL_MESSAGE,
    c.LANGUAGE_CODE,
    COALESCE(s.TOPIC, c.TOPIC) AS TOPIC,
    s.SENTIMENT_SCORE,
    CASE
        WHEN s.SENTIMENT_SCORE > 0 THEN 'positive'
        WHEN s.SENTIMENT_SCORE < 0 THEN 'negative'
        WHEN s.SENTIMENT_SCORE = 0 THEN 'neutral'
    END AS SENTIMENT_LABEL,
    c.CREATED_AT
FROM HEALTHCARE_DW.INSAAN.CONVERSATIONS c
LEFT JOIN HEALTHCARE_DW.INSAAN.CONVERSATION_SENTIMENT s ON s.CONVERSATION_ID = c.CONVERSATION_ID
LEFT JOIN HEALTHCARE_DW.CORE.PATIENTS p ON p.PATIENT_ID = c.PATIENT_ID
WHERE c.ROLE = 'user';

-- Backfill anything already logged.
CALL HEALTHCARE_DW.INSAAN.SCORE_CONVERSATIONS();
