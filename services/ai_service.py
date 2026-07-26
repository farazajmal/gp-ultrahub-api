import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from services.followup_service import needs_follow_up
from services.intent_service import extract_intent
from services.execution_service import execute_intent
from services.memory_service import (
    get_history,
    add_message,
)
from services.search_state_service import (
    get_search_state,
    update_search_state,
    clear_search_state,
)
from services.memory_service import (
    get_history,
    add_message,
)
from services.data_service import load_services_data

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


import re

GREETING_PATTERN = re.compile(
    r"^\s*(hi+|hey+|hello+|hiya|good\s?morning|good\s?afternoon|good\s?evening|greetings)[\s!.,]*$",
    re.IGNORECASE
)


def chat(session_id: str, message: str):

    # Save the user's message first
    add_message(
        session_id,
        "user",
        message
    )

    # Load updated conversation
    history = get_history(session_id)

    # Step 0: If it's just a plain greeting, respond warmly
    # instead of jumping straight into a follow-up question.
    if GREETING_PATTERN.match(message.strip()):

        reply = (
            "Hi there! I'm the GP Ultra Hub assistant. I can help you find "
            "the right doctor and get you to their booking page — just let "
            "me know what you'd like to be seen for, or which doctor you'd "
            "like to book."
        )

        add_message(
            session_id,
            "assistant",
            reply
        )

        return reply

    # Step 1: Decide whether we need more information
    follow_up = needs_follow_up(history)

    if follow_up["needs_follow_up"]:

        add_message(
            session_id,
            "assistant",
            follow_up["question"]
        )

        return follow_up["question"]

    # Step 2: Extract intent
    intent = extract_intent(history)
    print("\n========== INTENT ==========")
    print(json.dumps(intent, indent=2))
    print("============================\n")

    search_state = update_search_state(
        session_id,
        intent
    )
    print("\nSEARCH STATE:")
    print(json.dumps(search_state, indent=2, default=str))
    
    # Step 2.5: If the request is unrelated to finding a doctor,
    # don't try to search — just redirect politely.
    if search_state.get("intent") == "general":

        reply = (
            "I'm the GP Ultra Hub receptionist — I can help you find the "
            "right doctor or provider and get you to their booking page. "
            "Could you tell me what you'd like to be seen for, or which "
            "doctor you'd like to book?"
        )

        add_message(session_id, "assistant", reply)
        return reply

    # Step 2.6: Clinic info questions (services, locations, phone numbers)
    # — answered strictly from real scraped data, never invented.
    if search_state.get("intent") == "clinic_info":

        try:
            services_data = load_services_data()
        except Exception:
            services_data = None

        if not services_data:

            reply = (
                "I'm having trouble pulling up that information right now. "
                "You can find our full list of services and clinic details "
                "at https://gpultrahub.com.au/services/ or by calling your "
                "nearest clinic."
            )

            add_message(session_id, "assistant", reply)
            return reply

        clinic_info_prompt = f"""
You are the AI Receptionist for GP Ultra Hub, answering a question
about clinic services or locations.

Answer ONLY using the facts in the data below. Never invent services,
addresses, phone numbers, or details that are not explicitly present
in this data.

If the question cannot be answered from this data, say so honestly
and suggest the patient call their nearest clinic or visit
https://gpultrahub.com.au/services/ — do not guess.

Be warm, concise, and conversational. Do not mention APIs, JSON,
databases, scrapers, or any technical/internal terms.

Conversation:
{json.dumps(history, indent=2)}

Clinic Services and Locations Data:
{json.dumps(services_data, indent=2)}
"""

        response = client.responses.create(
            model="gpt-5.4-mini",
            input=clinic_info_prompt,
        )

        reply = response.output_text

        add_message(session_id, "assistant", reply)
        return reply

    # Step 3: If we don't know the clinic yet, ask first
    clinic = (search_state.get("clinic") or "").lower()
    
    # Step 3: If we don't know the clinic yet, ask first
    clinic = (search_state.get("clinic") or "").lower()

    if (
        search_state.get("intent") in ["search", "recommend", "availability_search"]
        and clinic == ""
        and not search_state.get("any_clinic")
        and not search_state.get("doctor")
    ):

        reply = (
            "Sure! Which GP Ultra Hub location would you prefer?\n\n"
            "• Gladstone\n"
            "• Calliope\n"
            "• Burnett Heads\n"
            "• Toowoomba Plaza\n\n"
            "If you don't mind which location, just let me know and I'll recommend the earliest suitable doctor across all clinics."
        )

        add_message(
            session_id,
            "assistant",
            reply
        )

        return reply

    # Step 4: Execute the search
    result = execute_intent(search_state)

    # Single search result
    if (
        result
        and result["type"] == "search"
        and len(result["data"]) == 1
    ):

        doctor = result["data"][0]

        reply = (
            f"{doctor['doctor']} is available at GP Ultra Hub "
            f"{doctor['clinic']}.\n\n"
            f"Next available: {doctor['availability']}\n\n"
            f"Book here:\n{doctor['booking_url']}\n\n"
            "Open the booking page to view all available appointment times."
        )

        add_message(session_id, "assistant", reply)
        return reply


    # Single recommendation
    if (
        result
        and result["type"] == "recommend"
        and result["data"]
    ):

        doctor = result["data"]

        reply = (
            f"{doctor['doctor']} is available at GP Ultra Hub "
            f"{doctor['clinic']}.\n\n"
            f"Next available: {doctor['availability']}\n\n"
            f"Book here:\n{doctor['booking_url']}\n\n"
            "Open the booking page to view all available appointment times."
        )

        add_message(session_id, "assistant", reply)
        return reply


    # Availability search — never claim a specific timeslot,
    # only show next-available + booking link for each doctor.
    if (
        result
        and result["type"] == "availability_search"
    ):

        doctors = result.get("data") or []

        if not doctors:

            reply = (
                "I couldn't find any providers matching that. Could you "
                "tell me a bit more about what you need, or which clinic "
                "you'd prefer?"
            )

            add_message(session_id, "assistant", reply)
            return reply

        lines = []

        for doctor in doctors:
            lines.append(
                f"**{doctor['doctor']}** — GP Ultra Hub {doctor['clinic']}\n"
                f"Next available: {doctor['availability']}\n"
                f"Book here: {doctor['booking_url']}"
            )

        reply = (
            "I can't check exact appointment times directly, but here's "
            "the provider who may suit you. Open the booking page to view "
            "all available times and choose what works best for your "
            "schedule:\n\n" + "\n\n".join(lines)
        )

        add_message(session_id, "assistant", reply)
        return reply


    # Recommend intent but no matching doctor found
    if (
        result
        and result["type"] == "recommend"
        and result["data"] is None
    ):

        requested_name = search_state.get("doctor")

        reply = (
            f"I'm sorry, I couldn't find a doctor named "
            f"\"{requested_name}\" at GP Ultra Hub. Could you double-check "
            "the spelling, or let me know what you'd like to be seen for "
            "and I can recommend the right doctor?"
        )

        add_message(session_id, "assistant", reply)
        return reply

    print("\nRESULT:")
    print(json.dumps(result, indent=2))
    # Step 5: If nothing was found, give a safe canned reply
    # (never let GPT answer with no instructions — that's what
    # caused it to invent a booking flow)
    if result is None:

        reply = (
            "I couldn't find a matching doctor for that. Could you double-check "
            "the name, or tell me what you'd like to be seen for so I can "
            "recommend the right GP Ultra Hub doctor?"
        )

        add_message(
            session_id,
            "assistant",
            reply
        )

        return reply

    # Pull these from the clinic system result
    requested_provider = result.get("requested_provider", "the requested specialist")
    used_provider = result.get("used_provider", "one of our available providers")

    # Step 6: Build receptionist prompt
    prompt = f"""
You are the AI Receptionist for GP Ultra Hub.

Your primary goal is to help patients choose the right GP Ultra Hub doctor and direct them to a booking page as quickly as possible.

You are a receptionist, not a doctor.

Do not diagnose, assess symptoms, provide treatment advice, discuss warning signs, recommend emergency departments, telehealth services or other clinics unless the user is clearly describing a life-threatening emergency.

Use the conversation history, extracted search information and clinic results below to answer.

Conversation:
{json.dumps(history, indent=2)}

Current Search:
{json.dumps(search_state, indent=2, default=str)}

Clinic Results:
{json.dumps(result, indent=2)}

--------------------------------------------------
YOUR PRIORITY
--------------------------------------------------

Always move the conversation toward booking an appointment.

Avoid unnecessary questions.

Only ask a question if it is required to recommend the correct doctor.

If the user already knows which doctor they want, or enough information has been provided to identify the correct doctor, do not ask any further questions. Immediately provide the appropriate booking link.

--------------------------------------------------
DOCTOR RECOMMENDATIONS
--------------------------------------------------

Recommend the most appropriate doctor from the clinic results.

Always include the supplied booking link.

Mention the next available appointment ONLY if it exists in the clinic results.

Never invent doctors, appointment times or booking links.

If the clinic results contain a single doctor:

- Do not ask what the appointment is for.
- Do not ask for a preferred date.
- Do not ask for a preferred time.
- Do not ask for a clinic if the clinic is already known.
- Simply introduce the doctor, mention the next available appointment if provided, and provide the booking link.
- Encourage the patient to open the booking page to view all available appointment times.

--------------------------------------------------
AVAILABILITY SEARCH
--------------------------------------------------

If Clinic Results contain:

"type": "availability_search"

then:

- Never claim any doctor is available at the patient's requested time.
- Ignore "preferred_time" when choosing doctors.
- Present every doctor returned by the clinic system.
- For each doctor, include:
  - doctor's name
  - clinic
  - next available appointment (exactly as supplied)
  - booking link
- Tell the patient they can open each doctor's booking page to view all available appointment times and choose the one that best suits their schedule.
- Do not rank doctors by how close their next appointment is to the requested time.
- Do not say "Dr X is available after 4pm" unless that exact appointment time exists in the clinic results.

--------------------------------------------------
PREFERRED TIMES
--------------------------------------------------

If Clinic Results has:

"type": "availability_search"

then:

- The clinic system cannot determine which doctors have appointments at the patient's requested time.
- Do NOT say "available today", "available after 4pm", or similar.
- Present the returned doctors as suitable providers.
- Show each doctor's next available appointment exactly as supplied.
- Include each doctor's booking link.
- Tell the patient they can open each booking page to view all available appointment times and choose one that best suits their schedule.

Example wording:

"The following GPs may be suitable for your appointment. You can open each booking page to view all available appointment times and choose one that best suits your schedule."


--------------------------------------------------
SKIN CANCER
--------------------------------------------------

GP Ultra Hub GPs assess and manage:

- skin cancer
- suspicious moles
- mole checks
- melanoma concerns
- skin lesions
- skin biopsies

Treat these as standard GP appointments.

--------------------------------------------------
STYLE
--------------------------------------------------

Be warm, friendly and concise.

Never mention:

- APIs
- databases
- internal systems
- technical limitations

Never say:

- "I can't see the doctor's schedule."
- "I only know the next appointment."
- "I don't have access."

Never collect patient information.

Never ask for:

- Full name
- Date of birth
- Phone number
- Email address
- Medicare details
- Preferred appointment date
- Preferred appointment time
- Any booking details

Those details are collected by the HotDoc booking page.

If enough information has already been provided to identify the correct doctor, do not ask any further questions.

Your job is to:

1. Identify the correct GP Ultra Hub doctor(s).
2. Mention the next available appointment if supplied by the clinic results.
3. Provide the booking link.
4. Tell the patient to open the booking page to view all available appointment times and complete their booking.

Do not collect information that HotDoc will collect.

Do not ask questions that the booking page will ask.

Your job ends once you have identified the correct doctor and provided the booking link.
"""

    response = client.responses.create(
        model="gpt-5.4-mini",
        input=prompt,
    )

    reply = response.output_text

    add_message(
        session_id,
        "assistant",
        reply
    )



    return reply
