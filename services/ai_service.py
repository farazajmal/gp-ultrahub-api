import json
import os
import re

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
from services.data_service import load_services_data

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

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

    # Step 0: Plain greeting check
    if GREETING_PATTERN.match(message.strip()):
        reply = (
            "Hi there! I'm the GP UltraHub assistant. I can help you find "
            "the right doctor and check their availability — just let "
            "me know what you'd like to be seen for, or which doctor or day "
            "you'd like to book."
        )
        add_message(session_id, "assistant", reply)
        return reply

    # Step 1: Extract intent & update search state
    intent = extract_intent(history)
    print("\n========== INTENT ==========")
    print(json.dumps(intent, indent=2))
    print("============================\n")

    search_state = update_search_state(session_id, intent)
    print("\nSEARCH STATE:")
    print(json.dumps(search_state, indent=2, default=str))

    # Step 2: Location check probing
    if search_state.get("asked_other_locations"):
        if intent.get("clinic"):
            search_state["clinic"] = intent["clinic"]
            search_state["any_clinic"] = False
            search_state["asked_other_locations"] = False
        else:
            is_affirmative = bool(
                re.search(r"^(yes|yeah|sure|ok|okay|please|yep|yup|definitely|of course|go ahead|check other|other|any)", message.strip(), re.I)
                or intent.get("any_clinic")
            )
            is_negative = bool(re.search(r"^(no|nope|nah|not now|no thanks|never mind)", message.strip(), re.I))

            if is_negative:
                search_state["asked_other_locations"] = False
                reply = "No problem! Please let me know if you'd like to check for different days, or if there is anything else I can help you with."
                add_message(session_id, "assistant", reply)
                return reply

            if is_affirmative:
                search_state["clinic"] = None
                search_state["any_clinic"] = True
                search_state["asked_other_locations"] = False

    # Step 2.5: Unrelated / general questions
    if search_state.get("intent") == "general":
        reply = (
            "I'm the GP UltraHub receptionist — I can help you find the "
            "right doctor or provider and get you to their booking page. "
            "Could you tell me what you'd like to be seen for, or which "
            "doctor you'd like to book?"
        )
        add_message(session_id, "assistant", reply)
        return reply

    # Step 2.6: Clinic info questions
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
You are the AI Receptionist for GP UltraHub, answering a question
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

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": clinic_info_prompt}],
        )

        reply = response.choices[0].message.content
        add_message(session_id, "assistant", reply)
        return reply

    # Step 2.7: Diagnostic questions
    if search_state.get("intent") == "diagnostic_question":
        last_doctor = search_state.get("last_recommended_doctor")
        if last_doctor:
            reply = (
                f"I'm an AI assistant, so I'm not able to diagnose or assess "
                f"that myself — but {last_doctor['doctor']} can take a "
                f"proper look and give you a clear answer.\n\n"
                f"Book here:\n{last_doctor['booking_url']}"
            )
        else:
            reply = (
                "I'm an AI assistant, so I'm not able to diagnose or assess "
                "that myself — but a doctor can take a proper look and give "
                "you a clear answer. Let me know what you'd like to be seen "
                "for, or which clinic you'd prefer, and I'll point you to "
                "the right doctor's booking page."
            )

        add_message(session_id, "assistant", reply)
        return reply

    # Step 3: Location Check
    clinic = (search_state.get("clinic") or "").strip().lower()
    has_clinic = bool(clinic) or search_state.get("any_clinic", False)
    has_doctor = bool(search_state.get("doctor"))

    if (
        search_state.get("intent") in ["search", "recommend", "availability_search"]
        and not has_clinic
        and not has_doctor
    ):
        reply = (
            "Which GP UltraHub location would you prefer?\n\n"
            "[choice: Gladstone]\n"
            "[choice: Calliope]\n"
            "[choice: Burnett Heads]\n"
            "[choice: Toowoomba Plaza]\n"
            "[choice: Any Location would be fine]"
        )
        add_message(session_id, "assistant", reply)
        return reply

    # Step 3.5: Reason / Illness / Problem Check
    is_availability_search = search_state.get("intent") == "availability_search"
    has_interest = bool(search_state.get("interest"))
    has_specific_provider = bool(search_state.get("provider_type") and search_state.get("provider_type") != "GP")
    has_preferred_time = bool(search_state.get("preferred_time"))
    already_asked_reason = search_state.get("reason_prompted", False)

    if not has_interest:
        for m in history:
            if m.get("role") == "user":
                c = m.get("content", "")
                if re.search(r'\b(check[-\s]?up|health check|routine check|general check|annual check|medical assessment)\b', c, re.I):
                    has_interest = True
                    search_state["interest"] = "General health check-up"
                    break

    if (
        has_clinic
        and not has_doctor
        and not has_interest
        and not has_specific_provider
        and not has_preferred_time
        and not is_availability_search
        and not already_asked_reason
    ):
        search_state["reason_prompted"] = True
        reply = (
            "Could you tell me what you'd like to be seen for, or what symptoms or illness you're experiencing?\n\n"
            "(If you're not sure, just let me know and I can recommend a General Practitioner for a standard consultation.)"
        )
        add_message(session_id, "assistant", reply)
        return reply

    if already_asked_reason and not has_interest and not has_doctor:
        search_state["provider_type"] = search_state.get("provider_type") or "GP"
        search_state["reason_prompted"] = False

    # Step 4: Execute the search
    result = execute_intent(search_state)

    has_no_match = (
        result is None
        or (result.get("type") == "search" and not result.get("data"))
        or (result.get("type") == "recommend" and not result.get("data"))
        or (result.get("type") == "availability_search" and not result.get("data"))
    )

    if has_no_match and search_state.get("clinic") and not search_state.get("any_clinic"):
        if search_state.get("asked_location_prompted"):
            search_state["asked_location_prompted"] = False
            search_state["asked_other_locations"] = False
            reply = (
                f"I couldn't find an available doctor matching that at GP UltraHub {search_state['clinic']}.\n\n"
                f"Would you like to try checking across all locations, or look for a different day?\n\n"
                "[choice: Check all locations]\n"
                "[choice: Try another day]"
            )
            add_message(session_id, "assistant", reply)
            return reply

        alt_state = dict(search_state)
        alt_state["clinic"] = None
        alt_state["any_clinic"] = True
        alt_result = execute_intent(alt_state)
        has_other_matches = bool(alt_result and alt_result.get("data"))
        search_state["asked_other_locations"] = True
        search_state["asked_location_prompted"] = True

        if has_other_matches:
            reply = (
                f"I couldn't find an available doctor matching that at GP UltraHub {search_state['clinic']}.\n\n"
                f"Would you like me to suggest available doctors from our other locations?\n\n"
                "[choice: Yes, check other locations]\n"
                "[choice: No, thank you]"
            )
        else:
            reply = (
                f"I couldn't find an available doctor matching that at GP UltraHub {search_state['clinic']}.\n\n"
                f"Would you like me to check another location?\n\n"
                "[choice: Gladstone]\n"
                "[choice: Calliope]\n"
                "[choice: Burnett Heads]\n"
                "[choice: Toowoomba Plaza]"
            )

        add_message(session_id, "assistant", reply)
        return reply

    # Single search result
    if (
        result
        and result["type"] == "search"
        and len(result["data"]) == 1
    ):
        doctor = result["data"][0]
        update_search_state(session_id, {"last_recommended_doctor": doctor})

        avail_text = doctor.get("availability_summary") or doctor.get("availability")
        reply = (
            f"**{doctor['doctor']}** is available at GP UltraHub {doctor['clinic']}.\n\n"
            f"Availability: {avail_text}\n\n"
            f"Book here:\n{doctor['booking_url']}"
        )
        add_message(session_id, "assistant", reply)
        return reply

    # Multiple search results
    if (
        result
        and result["type"] == "search"
        and result["data"]
        and len(result["data"]) > 1
    ):
        doctors = result["data"]
        lines = []
        for d in doctors:
            avail_text = d.get("availability_summary") or d.get("availability")
            lines.append(
                f"**{d['doctor']}** — GP UltraHub {d['clinic']}\n"
                f"Available: {avail_text}\n"
                f"Book here: {d['booking_url']}"
            )

        intro = "Here are the available options across our locations:" if search_state.get("any_clinic") else "Here are a few suitable options:"
        reply = (
            f"{intro}\n\n" + "\n\n".join(lines) +
            "\n\nYou can click any of the booking links above to select your preferred appointment time."
        )
        add_message(session_id, "assistant", reply)
        return reply

    # Search with no matches at all
    if (
        result
        and result["type"] == "search"
        and not result["data"]
    ):
        reply = (
            "I couldn't find any matching doctors for that time or service. "
            "Would you like to try a different day, or tell me a bit more about what you need?"
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
        update_search_state(session_id, {"last_recommended_doctor": doctor})

        interest = search_state.get("interest")
        role = doctor.get("role") or doctor.get("provider_type") or "GP"
        avail_text = doctor.get("availability_summary") or doctor.get("availability")

        if interest:
            reply = (
                f"**{doctor['doctor']}** is a great match for {interest} at GP UltraHub {doctor['clinic']}.\n\n"
                f"Available: {avail_text}\n\n"
                f"Book here:\n{doctor['booking_url']}"
            )
        else:
            reply = (
                f"**{doctor['doctor']}** ({role}) is available at GP UltraHub {doctor['clinic']}.\n\n"
                f"Available: {avail_text}\n\n"
                f"Book here:\n{doctor['booking_url']}"
            )

        add_message(session_id, "assistant", reply)
        return reply

    # Availability search
    if (
        result
        and result["type"] == "availability_search"
    ):
        doctors = result.get("data") or []
        if not doctors:
            reply = (
                "I couldn't find any providers matching that time or location. Could you "
                "try a different day or let me know which clinic you prefer?"
            )
            add_message(session_id, "assistant", reply)
            return reply

        lines = []
        for doctor in doctors:
            avail_text = doctor.get("availability_summary") or doctor.get("availability")
            lines.append(
                f"**{doctor['doctor']}** — GP UltraHub {doctor['clinic']}\n"
                f"Available: {avail_text}\n"
                f"Book here: {doctor['booking_url']}"
            )

        reply = (
            "Here are the available doctor options and their time patches:\n\n" +
            "\n\n".join(lines) +
            "\n\nYou can click any of the booking links above to select your appointment."
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
        if requested_name:
            reply = (
                f"I'm sorry, I couldn't find a doctor named \"{requested_name}\" at GP UltraHub. "
                "Could you double-check the spelling, or let me know what you'd like to be seen for?"
            )
        else:
            reply = (
                "I couldn't find a matching doctor for that. Could you tell me a bit more "
                "about what you need or if another location would work?"
            )
        add_message(session_id, "assistant", reply)
        return reply

    # Step 5: Fallback if result is None
    if result is None:
        reply = (
            "I couldn't find a matching doctor for that. Could you double-check the name, "
            "or tell me what you'd like to be seen for so I can recommend the right GP UltraHub doctor?"
        )
        add_message(session_id, "assistant", reply)
        return reply

    # Step 6: Receptionist prompt with time patch guidance
    prompt = f"""
You are the AI Receptionist for GP UltraHub.

Your primary goal is to help patients choose the right GP UltraHub doctor and direct them to a booking page as quickly as possible.

You are a receptionist, not a doctor.

Do not diagnose, assess symptoms, or discuss medical treatment.

Use the conversation history, extracted search information and clinic results below to answer.

Conversation:
{json.dumps(history, indent=2)}

Current Search:
{json.dumps(search_state, indent=2, default=str)}

Clinic Results:
{json.dumps(result, indent=2)}

--------------------------------------------------
TIME PATCHES & AVAILABILITY
--------------------------------------------------

Doctor availability is provided in time patches (ranges), e.g. "Monday from 10:00 am - 3:00 pm and 6:00 pm - 8:00 pm".

If the user asks whether a doctor is available on a specific day/time (e.g. "is Dr X available on Monday at 1pm?"):

- Compare 1pm against the time patches.
- If 1pm falls within a patch (e.g. 10:00 am - 3:00 pm), confirm that Dr X is available on Monday during that time patch.
- Present the time patch clearly (e.g., "Dr. X is available on Monday from 10:00 am to 3:00 pm and 6:00 pm to 8:00 pm").
- Provide the booking button link.

Style:
Be warm, friendly, and concise. Never mention internal technical terms, APIs, or databases.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    reply = response.choices[0].message.content
    add_message(session_id, "assistant", reply)
    return reply
