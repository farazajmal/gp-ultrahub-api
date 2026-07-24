import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


SYSTEM_PROMPT = """
You are helping rank doctors for GP Ultra Hub.

Your task is ONLY to score how medically suitable each doctor is for the patient's condition.

You are NOT choosing appointments.

You are NOT considering:

- availability
- clinic
- gender

Those are handled elsewhere.

You are ONLY comparing the doctor's medical experience and interests.

Return ONLY valid JSON.

Example:

{
    "Dr Shahid": 48,
    "Dr Mehwish": 36,
    "Dr Asma": 15
}

Rules:

- Maximum score = 50
- Minimum score = 0

50 = Excellent match
40 = Very good match
30 = Good match
20 = Acceptable
10 = Weak match
0 = Not relevant
"""


def score_medical_match(interest, doctors):

    if not interest:
        return {}

    doctor_profiles = []

    for doctor in doctors:

        doctor_profiles.append({
            "doctor": doctor["doctor"],
            "areas_of_interest": doctor.get("areas_of_interest", []),
            "bio": doctor.get("bio", ""),
            "qualifications": doctor.get("qualifications", [])
        })

    prompt = f"""
Patient condition:

{interest}

Doctors:

{json.dumps(doctor_profiles, indent=2)}

Return ONLY JSON.
"""

    response = client.responses.create(
        model="gpt-5.4-mini",
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return json.loads(response.output_text)