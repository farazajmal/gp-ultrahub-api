from collections import defaultdict
from datetime import datetime, timedelta

# Stores the current search state
search_states = defaultdict(dict)

# Search expires after 1 hour
SEARCH_TIMEOUT = timedelta(hours=1)


def _expired(session_id):

    state = search_states.get(session_id)

    if not state:
        return True

    updated = state.get("_updated")

    if not updated:
        return True

    return datetime.now() - updated > SEARCH_TIMEOUT


def get_search_state(session_id):

    if _expired(session_id):
        search_states.pop(session_id, None)
        return {}

    return search_states[session_id]


def update_search_state(session_id, intent):

    if _expired(session_id):
        search_states[session_id] = {}

    state = search_states[session_id]
    was_availability = state.get("intent") == "availability_search"

    for key, value in intent.items():
        if value is not None:
            if key == "day" and value == "CLEAR_DAY":
                state["day"] = None
                state["time_prompted"] = False
            else:
                state[key] = value

    # If any_time is selected, clear prior day if it was set
    if intent.get("preferred_time") and str(intent.get("preferred_time")).lower() in ["any time", "anytime", "any", "no preference", "whenever"]:
        state["day"] = None

    if intent.get("day") and str(state.get("preferred_time")).lower() in ["any time", "anytime", "any", "no preference", "whenever"]:
        state["preferred_time"] = None

    # If day, preferred_time, or prior availability_search is active in state, keep intent as availability_search unless specific interest/doctor override is given
    if (state.get("day") or state.get("preferred_time") or was_availability) and not intent.get("interest") and not intent.get("doctor"):
        state["intent"] = "availability_search"

    # Bind last_recommended_doctor if user asks a day availability question right after a doctor recommendation ("is she available on Friday?")
    if intent.get("intent") in ["availability_search", "search"]:
        if intent.get("doctor") is None and state.get("last_recommended_doctor") and intent.get("day"):
            state["doctor"] = state["last_recommended_doctor"].get("doctor")
            state["gender"] = None

    if intent.get("intent") == "recommend" and intent.get("doctor") is None:
        state["doctor"] = None

    # If any_clinic is requested, clear any previously locked specific clinic
    if intent.get("any_clinic"):
        state["clinic"] = None
        state["any_clinic"] = True
    elif intent.get("clinic"):
        state["any_clinic"] = False

    state["_updated"] = datetime.now()

    return state


def clear_search_state(session_id):

    search_states.pop(session_id, None)
