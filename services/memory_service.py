from collections import defaultdict

# Temporary in-memory storage
# Later we'll replace this with Redis.

sessions = defaultdict(list)


def get_history(session_id: str):
    return sessions[session_id]


def add_message(session_id: str, role: str, content: str):
    sessions[session_id].append({
        "role": role,
        "content": content
    })


def clear_history(session_id: str):
    sessions.pop(session_id, None)