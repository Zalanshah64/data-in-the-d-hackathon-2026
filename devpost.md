## Inspiration

My parents struggle with English and have a hard time navigating the medical world -- bills, appointments, prescriptions. They always said they just want to speak with "a human that understands them." That phrase stuck with me. I named the project **Insaan**, which means "human" in Urdu, because healthcare should feel human no matter what language you speak. I wanted to build a demo of what AI could actually do for people like my parents -- not a toy chatbot, but something that connects to real patient data and takes real actions on their behalf, in whatever language they're comfortable with.

## What it does

Insaan is a multilingual AI healthcare concierge. Patients chat with it in any language -- Arabic, Spanish, Hindi, or any of 23 supported languages -- and Insaan auto-detects the language, pulls their actual medical data, and responds in kind. Specifically, patients can:

- **Ask about insurance and billing** -- "Why do I pay so much more now?" gets a clear, data-driven cost breakdown with year-over-year trends
- **Schedule, reschedule, or cancel appointments** -- through natural conversation, with the AI writing changes directly to the database
- **Request prescription refills** -- validated against their pharmacy records
- **Find clinical trials** they may qualify for based on their diagnoses
- **View a fully translated patient portal** -- diagnoses, medications, costs, and upcoming visits all rendered in their preferred language

There's also an admin dashboard for the insurance company side, showing conversation volume, patient sentiment trends, languages served, self-serve actions completed, and an AI-generated executive summary.

## How we built it

The entire app runs natively on Snowflake:

- **Streamlit in Snowflake** powers the front-end: the chat interface, patient portal, and admin dashboard are all Streamlit pages deployed as a single app
- **Cortex Agent (DATA_AGENT_RUN)** is the brain -- it routes patient queries to the right data (appointments, billing, medications) and executes write-back actions through custom SQL stored procedures exposed as agent tools
- **AI_TRANSLATE** handles the multilingual pipeline: user input is translated to English for the agent, responses are translated back to the patient's language, and the entire patient portal UI is batch-translated in a single cached call
- **AI_CLASSIFY** detects the language of each message so the system knows how to respond without the patient ever having to pick a language
- **AI_SENTIMENT** and **AI_CLASSIFY** together power a sentiment and topic-tagging pipeline on every patient message, feeding the admin dashboard
- **AI_COMPLETE** generates an executive summary on the admin dashboard from conversation analytics
- **Semantic Views** give the Cortex Agent structured access to the healthcare data warehouse
- Custom **SQL stored procedures** handle every write-back action (BookAppointment, RescheduleAppointment, CancelAppointment, RequestRefill, UpdateInsurance) with input validation, duplicate-checking, and audit logging to a self-serve requests table

The data model spans multiple schemas -- CORE (patients, providers), CLINICAL (encounters, diagnoses), PHARMACY (prescriptions), BILLING (claims, payments), RESEARCH (clinical trials), and INSAAN (conversations, sentiment, self-serve requests).

## Challenges we ran into

- **Translation round-tripping** -- the Cortex Agent only works reliably in English, so every message has to be translated to English on the way in and back to the patient's language on the way out. Getting this pipeline to feel seamless (no visible lag, no garbled context) took iteration.
- **Agent tool design** -- the Cortex Agent needs well-structured tools to take real actions. Each stored procedure had to validate that the target record actually belongs to the requesting patient, handle edge cases (past dates, duplicate bookings, missing prescriptions), and log the action for audit -- all in SQL.
- **Keeping the chat conversational** -- passing conversation history to the agent in a way that maintains context across multi-turn exchanges, while staying within token limits, required careful prompt construction.
- **Portal translation at scale** -- the patient portal has dozens of dynamic strings (diagnoses, medication names, visit types, statuses). Translating them all in one batched AI_TRANSLATE call and caching the result was the key to keeping the page fast.
- **Dollar sign rendering** -- Streamlit interprets `$` as LaTeX delimiters, so every response containing dollar amounts had to be escaped before display.

## Accomplishments that we're proud of

- The app actually works end-to-end: a patient can type in Arabic asking to reschedule an appointment, and the system detects the language, finds the appointment, proposes a new date, confirms in Arabic, writes the change to the database, and refreshes the portal -- all in one conversation.
- The patient portal auto-translates the entire UI -- not just labels, but dynamic data like diagnosis descriptions, medication frequencies, and visit statuses.
- The admin dashboard gives the insurance company real operational value: sentiment alerts, topic breakdowns, language distribution, self-serve deflection metrics, and an AI-generated executive summary.
- Every write-back action is validated and audited. The system won't let you cancel someone else's appointment or book a visit with a doctor you've never seen.
- 23 languages supported with zero per-language configuration -- it's all handled by AI_CLASSIFY for detection and AI_TRANSLATE for translation.

## What we learned

- Snowflake's Cortex AI functions (AI_TRANSLATE, AI_CLASSIFY, AI_SENTIMENT, AI_COMPLETE) are production-ready building blocks that compose well together. Chaining them in a pipeline -- detect language, translate in, run agent, translate out, score sentiment -- felt natural.
- Cortex Agent with DATA_AGENT_RUN is powerful but opinionated. Designing the right tool interface (what parameters the procedures take, what they return) matters more than the prompt.
- Streamlit in Snowflake is a surprisingly capable app platform when you lean into session state and multi-page navigation. The sidebar-driven patient login, chat with streaming output, and data-heavy portal all work within the framework.
- Building for non-English speakers changes your assumptions about everything: error messages need to be translatable, UI labels can't be hardcoded, and you can't rely on the user reading status text in English.

## What's next for Insaan

- **Speech-to-text and text-to-speech** -- the biggest barrier for patients like my parents isn't just language, it's literacy. Letting them speak to Insaan out loud and hear responses back would remove that barrier entirely.
- **Conversation analytics and proactive outreach** -- using sentiment trends to flag frustrated patients so care coordinators can intervene before a complaint escalates.
- **Deeper medical knowledge** -- integrating clinical guidelines and drug interaction data so Insaan can give more informed, context-aware responses.
- **Multi-provider support** -- extending the platform to support multiple health systems, each with their own data, branding, and provider networks.
