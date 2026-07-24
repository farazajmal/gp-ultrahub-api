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

    state["_updated"] = datetime.now()

    return state


def clear_search_state(session_id):

    search_states.pop(session_id, None)