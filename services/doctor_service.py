from datetime import datetime, timedelta
import difflib
import re

from services.data_service import load_data
from utils.date_parser import parse_availability, match_patch_to_query
from services.ranking_service import score_medical_match


def _normalize_name(name):
    name = (name or "").lower()
    name = re.sub(r'^dr\.?\s*', '', name)
    return name.strip()


CLINIC_ALIASES = {
    "toowoomba plaza": "toowoomba",
    "toowoomba": "toowoomba",
    "gladstone": "gladstone",
    "calliope": "calliope",
    "burnett heads": "burnett heads",
    "burnett": "burnett heads",
}


def _normalize_clinic(name):
    if not name:
        return ""
    norm = name.strip().lower()
    for alias, canonical in CLINIC_ALIASES.items():
        if alias in norm or norm in alias:
            return canonical
    return norm


def _doctor_name_matches(query, doctor_name, cutoff=0.7):
    query_norm = _normalize_name(query)
    name_norm = _normalize_name(doctor_name)

    if query_norm in name_norm:
        return True

    query_words = query_norm.split()
    name_words = name_norm.split()

    if not query_words or not name_words:
        return False

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
        key=lambda doctor: parse_availability(doctor.get("availability"))
    )


def find_available_today():
    today = datetime.now().date()
    available = []
    for doctor in get_all_doctors():
        appointment = parse_availability(doctor.get("availability"))
        if appointment.date() == today:
            available.append(doctor)
    return available


def filter_doctor_patches(doctor_obj, day=None, preferred_time=None):
    """
    Extracts and filters matching availability patches for a doctor.
    Returns (has_match, matching_patches, patch_summary_str)
    """
    patches = doctor_obj.get("availability_patches") or []
    if not patches:
        # Fallback if no patches are present: return True only if no day/time filter requested
        if day or preferred_time:
            return False, [], ""
        return True, [], doctor_obj.get("availability", "")

    matching_patches = []
    for p in patches:
        if match_patch_to_query(p, day_query=day, time_query=preferred_time):
            matching_patches.append(p)

    if not matching_patches:
        return False, [], ""

    # Group matching patches by day for nice string representation
    by_day = {}
    for mp in matching_patches:
        d_name = mp.get("day_name")
        by_day.setdefault(d_name, []).append(mp.get("display"))

    summary_parts = []
    for d_name, times in by_day.items():
        summary_parts.append(f"{d_name} from " + " and ".join(times))

    patch_summary = ", ".join(summary_parts)
    return True, matching_patches, patch_summary


def search_doctors(
    doctor=None,
    clinic=None,
    day=None,
    preferred_time=None,
    provider_type=None,
    interest=None,
    gender=None,
):

    # ----------------------------
    # Direct doctor lookup
    # ----------------------------
    if doctor:
        filtered = []
        for item in get_all_doctors():
            doctor_name = item.get("doctor") or ""
            if not _doctor_name_matches(doctor, doctor_name):
                continue

            if clinic:
                doctor_clinic = item.get("clinic") or ""
                if _normalize_clinic(doctor_clinic) != _normalize_clinic(clinic):
                    continue

            has_match, matching_patches, patch_summary = filter_doctor_patches(item, day=day, preferred_time=preferred_time)
            if (day or preferred_time) and not has_match:
                continue

            doc_copy = dict(item)
            if matching_patches:
                doc_copy["matching_patches"] = matching_patches
                doc_copy["availability_summary"] = patch_summary
            filtered.append(doc_copy)

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

    for item in results:
        has_match, matching_patches, patch_summary = filter_doctor_patches(item, day=day, preferred_time=preferred_time)
        if (day or preferred_time) and not has_match:
            continue

        doc_copy = dict(item)
        if matching_patches:
            doc_copy["matching_patches"] = matching_patches
            doc_copy["availability_summary"] = patch_summary
        filtered.append(doc_copy)

    return filtered


def score_doctor(doctor, intent, medical_scores):
    score = 0

    clinic = intent.get("clinic")
    if clinic and not intent.get("any_clinic"):
        doctor_clinic = doctor.get("clinic") or ""
        if _normalize_clinic(doctor_clinic) != _normalize_clinic(clinic):
            return 0
        score += 20
    elif clinic and intent.get("any_clinic"):
        doctor_clinic = doctor.get("clinic") or ""
        if _normalize_clinic(doctor_clinic) == _normalize_clinic(clinic):
            score += 20

    provider_type = intent.get("provider_type")
    if provider_type:
        role = (doctor.get("role") or "").lower()
        provider = (doctor.get("provider_type") or "").lower()
        if provider_type.lower() in role or provider_type.lower() in provider:
            score += 60
        else:
            return 0

    gender = intent.get("gender")
    if gender:
        doctor_gender = (doctor.get("gender") or "").lower()
        if doctor_gender == gender.lower():
            score += 10
        else:
            return 0

    interest = intent.get("interest")
    if interest:
        med_score = medical_scores.get(doctor.get("doctor"), 0)
        score += med_score

    if not provider_type and not interest and not gender:
        score += 1

    return score


def rank_doctors(intent):
    doctors = get_all_doctors()
    interest = intent.get("interest")

    if interest:
        medical_scores = score_medical_match(interest, doctors)
    else:
        medical_scores = {}

    ranked = []
    for doctor in doctors:
        score = score_doctor(doctor, intent, medical_scores)
        if score > 0:
            ranked.append((score, doctor))

    ranked.sort(
        key=lambda item: (
            -item[0],
            parse_availability(item[1].get("availability"))
        )
    )

    return [doctor for _, doctor in ranked]


def recommend_doctor(intent):
    ranked = rank_doctors(intent)
    if not ranked:
        return None
    return ranked[0]


def availability_search(intent):
    if intent.get("interest"):
        doctors = rank_doctors(intent)
    else:
        doctors = get_all_doctors()

    provider_type = intent.get("provider_type")
    clinic = intent.get("clinic")
    any_clinic = intent.get("any_clinic", False)
    gender = intent.get("gender")
    day = intent.get("day")
    preferred_time = intent.get("preferred_time")

    results = []

    for doctor in doctors:
        requested_doctor = intent.get("doctor")
        if requested_doctor:
            doctor_name = doctor.get("doctor") or ""
            if not _doctor_name_matches(requested_doctor, doctor_name):
                continue

        if provider_type:
            role = (doctor.get("role") or "").lower()
            provider = (doctor.get("provider_type") or "").lower()
            if provider_type.lower() not in role and provider_type.lower() not in provider:
                continue

        if clinic and not any_clinic:
            doctor_clinic = doctor.get("clinic") or ""
            if _normalize_clinic(doctor_clinic) != _normalize_clinic(clinic):
                continue

        if gender:
            doctor_gender = (doctor.get("gender") or "").lower()
            if doctor_gender != gender.lower():
                continue

        if not doctor.get("availability") and not doctor.get("availability_patches"):
            continue

        has_match, matching_patches, patch_summary = filter_doctor_patches(doctor, day=day, preferred_time=preferred_time)
        if (day or preferred_time) and not has_match:
            continue

        doc_copy = dict(doctor)
        if matching_patches:
            doc_copy["matching_patches"] = matching_patches
            doc_copy["availability_summary"] = patch_summary
        results.append(doc_copy)

    results.sort(
        key=lambda doctor: parse_availability(doctor.get("availability"))
    )

    return results[:5]
