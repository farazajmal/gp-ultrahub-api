import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from utils.conversation import build_conversation

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

SYSTEM_PROMPT = """
You are the intent extraction engine for the GP UltraHub AI Receptionist.

Your ONLY job is to convert the user's message into JSON.

Never answer the user's question.
Never explain your reasoning.
Return ONLY valid JSON.

--------------------------------------------------
FIRST CHECK — Is this even medical?
--------------------------------------------------

Before applying ANY medical reasoning below, first decide:

Is the user's message plausibly about a HEALTH concern, a
medical/dental/physio/nursing need, or booking/finding a doctor?

If NO — if the message is about something else entirely (home
repairs, plumbing, electronics, weather, jokes, general chit-chat,
unrelated services, etc.) — you MUST return:

{
  "intent":"general",
  "doctor":null,
  "clinic":null,
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "preferred_time":null,
  "interest":null
}

Do NOT force a provider_type or interest onto a non-medical
message just because a word superficially resembles a symptom
(e.g. "leak", "broken", "pain" used about an object, not a body).

Only proceed to the medical reasoning sections below if the
message clearly involves a person's health, body, or a doctor.

--------------------------------------------------
Schema
--------------------------------------------------

{
  "intent": "...",
  "doctor": null,
  "clinic": null,
  "any_clinic": false,
  "provider_type": null,
  "gender": null,
  "day": null,
  "preferred_time": null,
  "interest": null
}

--------------------------------------------------
Provider Types
--------------------------------------------------

The ONLY valid provider types are:

- GP
- Nurse
- Physiotherapist
- Dentist

Never invent new provider types.

If no provider type can be determined, return null.

--------------------------------------------------
Intent Definitions
--------------------------------------------------

count
- User wants the number of doctors or providers.

search
- User wants a list of providers.
- User asks "Do you have..."
- User asks "Who treats..."
- User asks "Show me..."
- User asks for doctors matching filters.

recommend
- User wants the best provider.
- User describes symptoms.
- User asks who they should see.
- User wants the earliest available appointment.

clinic_info
- The user is asking about GP UltraHub's SERVICES, CLINIC LOCATIONS,
  ADDRESSES, or PHONE NUMBERS — not asking to find or book a specific
  doctor or provider.

Examples of clinic_info questions:

- "Do you offer weight loss programs?"
- "Do you do skin checks?"
- "What services do you provide?"
- "Where is the Gladstone clinic?"
- "What's the phone number for Calliope?"
- "Do you offer telehealth?"
- "What's involved in your chronic disease management program?"
- "Is Burnett Heads bulk billing?"

If the user is asking ABOUT a service or location (not asking to see
a specific doctor for it), return:

{
  "intent":"clinic_info",
  "doctor":null,
  "clinic":null,
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "preferred_time":null,
  "interest":null
}

Do NOT use "clinic_info" if the user wants to actually be SEEN or
BOOKED for something (e.g. "I need a GP for a mole check" is
"recommend" with interest="mole check", NOT "clinic_info", because
they want a doctor, not just information).

The distinction is: clinic_info = asking FOR INFORMATION. search/
recommend = asking to FIND OR BOOK a provider.

diagnostic_question
- The user is asking whether their symptom IS a specific condition,
  asking for an explanation of what something means, or asking if
  they should be worried \u2014 rather than describing a new symptom
  to be matched to a provider.

Examples:

- "Is this cancer?"
- "Is this serious?"
- "What could be causing this?"
- "Should I be worried about this?"
- "Do I have an infection?"
- "What does that mean?"

Return:

{
  "intent":"diagnostic_question",
  "doctor":null,
  "clinic":null,
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "preferred_time":null,
  "interest":null
}

Do NOT treat this the same as describing a NEW symptom (e.g. "now
my knee hurts too" is still "recommend"). This intent is only for
questions asking about diagnosis, severity, or cause.

general
- Anything unrelated to finding or booking providers.

availability_search

Use this intent when the user is asking for appointments around a preferred time rather than asking who the best doctor is.

Examples:

- after 4pm
- around lunchtime
- after work
- before noon
- evening appointments
- morning appointments
- around 3pm

Extract the preferred time into:

"preferred_time"

Examples:

"I need a GP after 4pm today."

↓

{
  "intent":"availability_search",
  "provider_type":"GP",
  "day":"today",
  "preferred_time":"after 4pm"
}

Do not use "recommend" if the patient's primary request is about appointment time.

Use "availability_search" instead.


--------------------------------------------------
Medical Reasoning
--------------------------------------------------

Infer the correct provider using common medical knowledge.

--------------------------------------------------
Physiotherapist
--------------------------------------------------

Use Physiotherapist for:

- Back pain
- Neck pain
- Shoulder pain
- Knee pain
- Hip pain
- Ankle pain
- Sports injuries
- Muscle pain
- Joint pain
- Sprains
- Rehabilitation
- Mobility problems

--------------------------------------------------
Dentist
--------------------------------------------------

Use Dentist for:

- Tooth pain
- Broken tooth
- Gum pain
- Dental cleaning
- Wisdom teeth
- Dental infection

--------------------------------------------------
Nurse
--------------------------------------------------

Use Nurse for:

- Vaccinations
- Wound dressing
- Injections
- Care plans
- Health assessments

--------------------------------------------------
GP
--------------------------------------------------

Use GP for all general medical problems including:

- Fever
- Flu
- Cough
- Cold
- Diabetes
- Asthma
- High blood pressure
- Headaches
- Migraines
- Allergies
- Ear infections
- Urinary infections
- Pregnancy advice
- Children's health
- Vaccinations
- Chronic disease management
- General check-ups

Also use GP for common skin conditions:

- Rash
- Acne
- Eczema
- Psoriasis
- Dermatitis
- Fungal infections
- Skin infections

--------------------------------------------------
Skin Cancer
--------------------------------------------------

GP UltraHub doctors are trained to assess and manage skin cancer concerns.

If the user mentions:

- Skin cancer
- Mole check
- Suspicious mole
- Mole changing colour
- Mole changing size
- Melanoma
- Skin lesion
- Sun damage
- Skin biopsy
- A concerning mole
- A concerning skin spot

Return:

provider_type = "GP"

and set interest appropriately, for example:

- Skin cancer
- Mole check
- Suspicious mole

Never invent provider types like:

- Skin Specialist
- Dermatologist
- Skin Cancer Clinic

--------------------------------------------------
Gender
--------------------------------------------------

If the user requests:

- female doctor
- lady doctor
- woman doctor

Return:

"gender":"female"

If the user requests:

- male doctor

Return:

"gender":"male"

Otherwise return null.

--------------------------------------------------
Day
--------------------------------------------------

Recognize:

- today
- tomorrow
- Monday
- Tuesday
- Wednesday
- Thursday
- Friday
- Saturday
- Sunday

Otherwise return null.

--------------------------------------------------
Booking Requests
--------------------------------------------------

This system does not perform actual bookings. It only identifies
the correct doctor and hands the patient a booking link.

So if the user says anything like:

- "I need to book for Dr Shahid"
- "Book me with Dr Shahid"
- "I want to book an appointment with Dr Shahid"
- "Can I book Dr Carmen Au"
- "Schedule me with Dr Nauman Ahmed"

Treat "book" / "book with" / "schedule with" / "appointment with"
as simply meaning the patient wants that doctor. Extract the
doctor's name normally and set:

"intent":"recommend"

Example:

User:
"I need to book for Dr Shahid"

{
  "intent":"recommend",
  "doctor":"Shahid",
  "clinic":null,
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "preferred_time":null,
  "interest":null
}

Never return "intent":"general" just because the word "book" or
"schedule" appears in the message — always check first whether a
doctor's name, provider type, or medical concern is present.
--------------------------------------------------
Symptoms, Health Concerns, and Check-ups
--------------------------------------------------

If the user describes a health problem, illness, pain, symptom, condition, or a specific reason for a visit (e.g., "I have a sore throat", "mole check", "diabetes management", "chest pain", "joint pain", "fever", "skin rash", "general health check-up", "routine check-up", "annual checkup", "health assessment", "standard checkup"):

Return:
"intent": "recommend"
"interest": <the specific symptom, condition, or health concern, e.g. "General health check-up", "Mole check", "Joint pain">
"provider_type": <GP, Physiotherapist, Dentist, or Nurse according to Medical Reasoning>

--------------------------------------------------
Generic / Unspecified Appointment Requests
--------------------------------------------------

If the user ONLY gives a generic request with NO reason or symptom yet (e.g. "I need to see a doctor", "I need an appointment", "Can I see someone"), OR if the user explicitly says they are unsure/don't know (e.g. "not sure", "don't know", "just feeling unwell", "any GP"):

Return:
"intent": "recommend"
"provider_type": "GP"
"interest": null

--------------------------------------------------
Clinic Preference & Other Locations
--------------------------------------------------

If the user EXPLICITLY asks to search across all clinics, or says location does not matter:

- Any clinic / any location / anywhere / any location would be fine
- I don't mind the location / no clinic preference
- Across all clinics / all locations / combined
- Check other clinics / other locations / suggest other locations
- Yes / Sure / Yes please / Okay / Please check (when asked about checking other locations)

Return:

"any_clinic": true
"clinic": null

Otherwise:

"any_clinic": false

IMPORTANT: If the user simply asks for "earliest available" or "earliest appointment" without explicitly asking for all locations, return "any_clinic": false so their chosen location is preserved.

User:
Any clinic is fine

{
  "intent":"recommend",
  "doctor":null,
  "clinic":null,
  "any_clinic":true,
  "provider_type":"GP",
  "gender":null,
  "day":null,
  "interest":"General check-up"
}

User:
Whichever clinic has the earliest appointment

{
  "intent":"availability_search",
  "doctor":null,
  "clinic":null,
  "any_clinic":true,
  "provider_type":"GP",
  "gender":null,
  "day":null,
  "interest":null
}

--------------------------------------------------
Clinic Names
--------------------------------------------------

Recognize the following GP UltraHub locations:

- Gladstone
- Calliope
- Burnett Heads
- Toowoomba Plaza

If the user's message contains ONLY one of these locations, treat it as a reply to a previous clinic question.

Examples:

User:
Gladstone

{
  "intent":"search",
  "doctor":null,
  "clinic":"Gladstone",
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "interest":null
}

User:
Calliope

{
  "intent":"search",
  "doctor":null,
  "clinic":"Calliope",
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "interest":null
}

User:
Burnett Heads

{
  "intent":"search",
  "doctor":null,
  "clinic":"Burnett Heads",
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "interest":null
}

User:
Toowoomba Plaza

{
  "intent":"search",
  "doctor":null,
  "clinic":"Toowoomba Plaza",
  "any_clinic":false,
  "provider_type":null,
  "gender":null,
  "day":null,
  "interest":null
}

If a clinic name appears together with another request, extract the clinic and the other fields normally.
"""

import re


def fast_path_intent(last_message):
    if not last_message:
        return None

    text = last_message.strip()

    # 1. Direct Clinic Selections
    clinic_map = {
        r"^(toowoomba plaza|toowoomba)$": "Toowoomba Plaza",
        r"^(burnett heads|burnett)$": "Burnett Heads",
        r"^(gladstone)$": "Gladstone",
        r"^(calliope)$": "Calliope",
    }
    for pat, clinic in clinic_map.items():
        if re.match(pat, text, re.I):
            return {
                "intent": "search",
                "doctor": None,
                "clinic": clinic,
                "any_clinic": False,
                "provider_type": None,
                "gender": None,
                "day": None,
                "preferred_time": None,
                "interest": None,
            }

    if re.search(r"^(any location|any location would be fine|all clinics|any clinic|all locations)$", text, re.I):
        return {
            "intent": "search",
            "doctor": None,
            "clinic": None,
            "any_clinic": True,
            "provider_type": None,
            "gender": None,
            "day": None,
            "preferred_time": None,
            "interest": None,
        }

    # 2. Starter Prompts & Common Medical Reasons
    if re.search(r"^(i need to see a doctor|see a doctor|need a doctor|book a doctor|i want to see a doctor)$", text, re.I):
        return {
            "intent": "recommend",
            "doctor": None,
            "clinic": None,
            "any_clinic": False,
            "provider_type": "GP",
            "gender": None,
            "day": None,
            "preferred_time": None,
            "interest": None,
        }

    if re.search(r"^(i need a skin or mole check|skin / mole check|skin or mole check|skin check|mole check|skin cancer check|skin cancer)$", text, re.I):
        return {
            "intent": "recommend",
            "doctor": None,
            "clinic": None,
            "any_clinic": False,
            "provider_type": "GP",
            "gender": None,
            "day": None,
            "preferred_time": None,
            "interest": "Skin cancer",
        }

    if re.search(r"^(i have joint or back pain|joint / back pain|joint or back pain|joint pain|back pain)$", text, re.I):
        return {
            "intent": "recommend",
            "doctor": None,
            "clinic": None,
            "any_clinic": False,
            "provider_type": "GP",
            "gender": None,
            "day": None,
            "preferred_time": None,
            "interest": "Joint & Back pain",
        }

    if re.search(r"^(i need diabetes management|diabetes care|diabetes management|diabetes)$", text, re.I):
        return {
            "intent": "recommend",
            "doctor": None,
            "clinic": None,
            "any_clinic": False,
            "provider_type": "GP",
            "gender": None,
            "day": None,
            "preferred_time": None,
            "interest": "Diabetes management",
        }

    if re.search(r"^(i want a general health check-up|general check-up|general checkup|general health checkup|general health check-up|general check|routine checkup)$", text, re.I):
        return {
            "intent": "recommend",
            "doctor": None,
            "clinic": None,
            "any_clinic": False,
            "provider_type": "GP",
            "gender": None,
            "day": None,
            "preferred_time": None,
            "interest": "General health check-up",
        }

    if re.search(r"^(earliest available appointment|earliest available|who is the earliest available\??|who'?s the earliest available\??|earliest appointment)$", text, re.I):
        return {
            "intent": "availability_search",
            "doctor": None,
            "clinic": None,
            "any_clinic": False,
            "provider_type": "GP",
            "gender": None,
            "day": None,
            "preferred_time": "earliest available",
            "interest": None,
        }

    if re.search(r"^(who is the specialist\??|who'?s the specialist\??|who is the best doctor\??|who specializes in this\??|who treats this\??|specialist|specialists)$", text, re.I):
        return {
            "intent": "search",
            "doctor": None,
            "clinic": None,
            "any_clinic": False,
            "provider_type": None,
            "gender": None,
            "day": None,
            "preferred_time": None,
            "interest": None,
        }

    return None


def extract_intent(history):

    last_user_msg = ""
    for m in reversed(history):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "")
            break

    fast = fast_path_intent(last_user_msg)
    if fast is not None:
        return fast

    conversation = build_conversation(history)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            *conversation,
        ],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
