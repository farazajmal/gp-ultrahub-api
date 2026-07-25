from datetime import datetime, timedelta

from services.data_service import load_data
from utils.date_parser import parse_availability
from services.ranking_service import score_medical_match


import difflib
import re


def _normalize_name(name):
    name = (name or "").lower()
    name = re.sub(r'^dr\.?\s*', '', name)
    return name.strip()


def _doctor_name_matches(query, doctor_name, cutoff=0.7):
    query_norm = _normalize_name(query)
    name_norm = _normalize_name(doctor_name)

    # Fast path: exact substring match (handles correct spellings as before)
    if query_norm in name_norm:
        return True

    query_words = query_norm.split()
    name_words = name_norm.split()

    if not query_words or not name_words:
        return False

    # Word-by-word fuzzy match, so "Javed" still matches "Javaid"
    for qw in query_words:
        best_ratio = max(
            (difflib.SequenceMatcher(None, qw, nw).ratio() for nw in name_words),
            default=0
        )
        if best_ratio < cutoff:
            return False

    return True

def get_all_doctors():
    data = load_data()

    doctors = []

    for clinic in data["clinics"].values():
        doctors.extend(clinic)

    return doctors


def find_earliest():
    doctors = get_all_doctors()

    if not doctors:
        return None

    return min(
        doctors,
        key=lambda doctor: parse_availability(
            doctor["availability"]
        )
    )


def find_available_today():
    today = datetime.now().date()

    available = []

    for doctor in get_all_doctors():

        appointment = parse_availability(
            doctor["availability"]
        )

        if appointment.date() == today:
            available.append(doctor)

    return available


def search_doctors(
    doctor=None,
    clinic=None,
    day=None,
    provider_type=None,
    interest=None,
    gender=None,
):

    # ----------------------------
    # Direct doctor lookup
    # ----------------------------
    if doctor:

        filtered = []

        today = datetime.now().date()

        for item in get_all_doctors():

            doctor_name = item.get("doctor") or ""

            if not _doctor_name_matches(doctor, doctor_name):
                continue

            if clinic:

                doctor_clinic = (item.get("clinic") or "").lower()

                if doctor_clinic != clinic.lower():
                    continue

            if day:

                appointment_date = parse_availability(
                    item["availability"]
                ).date()

                if day.lower() == "today":

                    if appointment_date != today:
                        continue

                elif day.lower() == "tomorrow":

                    if appointment_date != today + timedelta(days=1):
                        continue

            filtered.append(item)

        return filtered

    # ----------------------------
    # Normal ranking search
    # ----------------------------

    intent = {
        "doctor": doctor,
        "clinic": clinic,
        "provider_type": provider_type,
        "interest": interest,
        "gender": gender,
    }

    results = rank_doctors(intent)

    filtered = []

    today = datetime.now().date()

    for item in results:

        if day:

            appointment_date = parse_availability(
                item["availability"]
            ).date()

            if day.lower() == "today":

                if appointment_date != today:
                    continue

            elif day.lower() == "tomorrow":

                if appointment_date != today + timedelta(days=1):
                    continue

        filtered.append(item)

    return filtered


def score_doctor(doctor, intent, medical_scores):
    
    score = 0

    # ----------------------------
    # Provider Type
    # ----------------------------

    provider_type = intent.get("provider_type")

    if provider_type:

        role = (doctor.get("role") or "").lower()
        provider = (doctor.get("provider_type") or "").lower()

        if provider_type.lower() in role:
            score += 60

        elif provider_type.lower() in provider:
            score += 60

    # ----------------------------
    # Interests
    # ----------------------------

    interest = intent.get("interest")

    if interest:

        # Skin cancer stays as a business rule
        if interest.lower() == "skin cancer":

            if (doctor.get("provider_type") or "") == "GP":
                score += 40

        else:

            score += medical_scores.get(
                doctor["doctor"],
                0
            )

    # ----------------------------
    # Clinic
    # ----------------------------

    clinic = intent.get("clinic")

    if clinic:

        doctor_clinic = (doctor.get("clinic") or "").lower()

        if doctor_clinic == clinic.lower():
            score += 20

    # ----------------------------
    # Gender
    # ----------------------------

    gender = intent.get("gender")

    if gender:

        doctor_gender = (doctor.get("gender") or "").lower()

        if doctor_gender == gender.lower():
            score += 10

    return score


def rank_doctors(intent):

    doctors = get_all_doctors()

    interest = intent.get("interest")

    if interest:
        medical_scores = score_medical_match(
            interest,
            doctors
        )
    else:
        medical_scores = {}

    ranked = []

    for doctor in doctors:

        score = score_doctor(
            doctor,
            intent,
            medical_scores
        )

        if score > 0:
            ranked.append(
                (score, doctor)
            )

    ranked.sort(
        key=lambda item: (
            -item[0],
            parse_availability(
                item[1]["availability"]
            )
        )
    )

    return [
        doctor
        for _, doctor in ranked
    ]


def recommend_doctor(intent):

    ranked = rank_doctors(intent)

    if not ranked:
        return None

    return ranked[0]



def availability_search(intent):

    # If the patient mentioned a medical concern,
    # keep doctors medically ranked.
    if intent.get("interest"):
        doctors = rank_doctors(intent)
    else:
        doctors = get_all_doctors()

    provider_type = intent.get("provider_type")
    clinic = intent.get("clinic")
    any_clinic = intent.get("any_clinic", False)
    gender = intent.get("gender")

    results = []

    for doctor in doctors:

        # ----------------------------
        # Doctor
        # ----------------------------

        requested_doctor = intent.get("doctor")

        if requested_doctor:

            doctor_name = doctor.get("doctor") or ""

            if not _doctor_name_matches(requested_doctor, doctor_name):
                continue

        # ----------------------------
        # Provider Type
        # ----------------------------

        if provider_type:

            role = (doctor.get("role") or "").lower()
            provider = (doctor.get("provider_type") or "").lower()

            if (
                provider_type.lower() not in role
                and provider_type.lower() not in provider
            ):
                continue

        # ----------------------------
        # Clinic
        # ----------------------------

        if clinic and not any_clinic:

            doctor_clinic = (doctor.get("clinic") or "").lower()

            if doctor_clinic != clinic.lower():
                continue

        # ----------------------------
        # Gender
        # ----------------------------

        if gender:

            doctor_gender = (doctor.get("gender") or "").lower()

            if doctor_gender != gender.lower():
                continue

        # ----------------------------
        # Must have availability
        # ----------------------------

        if not doctor.get("availability"):
            continue

        results.append(doctor)

    # Earliest appointments first
    results.sort(
        key=lambda doctor: parse_availability(
            doctor["availability"]
        )
    )

    # Only return the first five doctors
    return results[:5]
