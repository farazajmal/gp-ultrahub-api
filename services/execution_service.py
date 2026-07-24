from services.doctor_service import (
    get_all_doctors,
    recommend_doctor,
    search_doctors,
    find_earliest,
    find_available_today,
    availability_search,
)

FALLBACK_PROVIDERS = {
    "Skin Specialist": "GP",
}


def execute_intent(intent: dict):

    action = intent.get("intent")

    # ----------------------------------------
    # COUNT
    # ----------------------------------------

    if action == "count":

        return {
            "type": "count",
            "data": len(get_all_doctors())
        }

    # ----------------------------------------
    # SEARCH
    # ----------------------------------------

    elif action == "search":

        doctors = search_doctors(
            doctor=intent.get("doctor"),
            clinic=intent.get("clinic"),
            provider_type=intent.get("provider_type"),
            day=intent.get("day"),
            interest=intent.get("interest"),
            gender=intent.get("gender"),
        )

        # Try fallback provider if nothing found
        if not doctors:

            provider = intent.get("provider_type")
            fallback = FALLBACK_PROVIDERS.get(provider)

            if fallback:

                doctors = search_doctors(
                    doctor=intent.get("doctor"),
                    clinic=intent.get("clinic"),
                    provider_type=fallback,
                    day=intent.get("day"),
                    interest=intent.get("interest"),
                    gender=intent.get("gender"),
                )

                return {
                    "type": "search",
                    "data": doctors,
                    "fallback": True,
                    "requested_provider": provider,
                    "used_provider": fallback,
                }

        return {
            "type": "search",
            "data": doctors,
            "fallback": False,
        }

    # ----------------------------------------
    # RECOMMEND
    # ----------------------------------------

    elif action == "recommend":

        # If a specific doctor was requested,
        # return that doctor directly.
        if intent.get("doctor"):

            print("Requested doctor:", intent.get("doctor"))

            doctors = search_doctors(
                doctor=intent.get("doctor")
            )

            print("Matched doctors:", [d["doctor"] for d in doctors])

            if doctors:
                return {
                    "type": "recommend",
                    "data": doctors[0]
                }

            return {
                "type": "recommend",
                "data": None
            }

        doctor = recommend_doctor(intent)

        return {
            "type": "recommend",
            "data": doctor
        }

    # ----------------------------------------
    # AVAILABILITY SEARCH
    # ----------------------------------------

    elif action == "availability_search":

        doctors = availability_search(intent)

        return {
            "type": "availability_search",
            "data": doctors,
            "preferred_time": intent.get("preferred_time"),
        }

    # ----------------------------------------
    # UNKNOWN
    # ----------------------------------------

    return None