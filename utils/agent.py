import json
from datetime import date
import streamlit as st

AGENT_FQN = "HEALTHCARE_DW.INSAAN.INSAAN_AGENT"

ACTION_TOOLS = {
    "CancelAppointment": "Appointment cancelled",
    "RescheduleAppointment": "Appointment rescheduled",
    "UpdateInsurance": "Insurance updated",
    "RequestRefill": "Refill requested",
    "BookAppointment": "Appointment booked",
}


def call_agent(session, user_message, patient_info, messages):
    """Return (response_text, actions) where actions lists the write tools the agent ran."""
    today = date.today()
    context = (
        f"I am patient {patient_info['full_name']} (PATIENT_ID {patient_info['patient_id']}). "
        f"Today is {today:%A, %Y-%m-%d}. "
    )
    full_message = context + user_message

    history = messages[:-1][-6:]
    if history:
        transcript = "\n".join(
            f"{'Patient' if m['role'] == 'user' else 'Insaan'}: {m.get('content_en', m['content'])}"
            for m in history
        )
        full_message = (
            f"{context}\n\nEarlier in this conversation:\n{transcript}\n\n"
            f"New question: {user_message}"
        )

    payload = json.dumps(
        {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": full_message}]}
            ]
        }
    )

    result = session.sql(
        f"""
        SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
            '{AGENT_FQN}',
            $${payload}$$,
            TRUE
        ) AS response
        """
    ).collect()

    if result:
        response = json.loads(result[0]["RESPONSE"])
        if "content" in response:
            text_parts = [
                item.get("text", "")
                for item in response["content"]
                if item.get("type") == "text"
            ]
            actions = [
                ACTION_TOOLS[name]
                for item in response["content"]
                if item.get("type") == "tool_use"
                and (name := item.get("tool_use", {}).get("name")) in ACTION_TOOLS
            ]
            text = (
                "\n".join(text_parts)
                if text_parts
                else "I processed your request but couldn't generate a text response."
            )
            return text, actions
        elif "message" in response:
            return f"Error: {response['message']}", []
    return "Sorry, I couldn't get a response. Please try again.", []
