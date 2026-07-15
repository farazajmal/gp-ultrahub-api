from datetime import datetime, timedelta

from services.data_service import load_data
from utils.date_parser import parse_availability


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
):
    doctors = get_all_doctors()
    results = []

    for item in doctors:

        if doctor and doctor.lower() not in item["doctor"].lower():
            continue

        if clinic and clinic.lower() != item["clinic"].lower():
            continue

        if provider_type:
            if item.get("provider_type", "").lower() != provider_type.lower():
                continue

        if day:
            appointment_date = parse_availability(
                item["availability"]
            ).date()

            today = datetime.now().date()

            if day.lower() == "today":
                if appointment_date != today:
                    continue

            elif day.lower() == "tomorrow":
                if appointment_date != today + timedelta(days=1):
                    continue

        results.append(item)

    results.sort(
        key=lambda doctor: parse_availability(
            doctor["availability"]
        )
    )

    return results


def recommend_doctor(
    clinic=None,
    day=None,
    provider_type=None,
):

    doctors = search_doctors(
        clinic=clinic,
        day=day,
        provider_type=provider_type,
    )

    if not doctors:
        return None

    # Skip nurses by default
    for doctor in doctors:

        if "nurse" not in doctor["doctor"].lower():
            return doctor

    # If only nurses exist, return the earliest nurse
    return doctors[0]