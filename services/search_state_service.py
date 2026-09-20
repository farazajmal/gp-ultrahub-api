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

    for key, value in intent.items():
        if value is not None:
            state[key] = value

    # If user conducts an availability search or clinic search without specifying a doctor or interest,
    # clear previously locked doctor/interest so the search checks ALL available providers at that location.
    # HOWEVER, if user asks a day availability question right after a doctor recommendation ("is she available on Friday?"),
    # bind the inquiry to the last_recommended_doctor!
    if intent.get("intent") in ["availability_search", "search"]:
        if intent.get("interest") is None and not intent.get("doctor"):
            state["interest"] = None
        if intent.get("doctor") is None and not state.get("last_recommended_doctor"):
            state["doctor"] = None
        elif intent.get("doctor") is None and state.get("last_recommended_doctor") and intent.get("day"):
            state["doctor"] = state["last_recommended_doctor"].get("doctor")
            state["gender"] = None

    if intent.get("intent") == "recommend" and intent.get("doctor") is None:
        state["doctor"] = None

    if intent.get("clinic") and intent.get("interest") is None:
        state["interest"] = None

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
