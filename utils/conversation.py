def build_conversation(history):

    conversation = []

    for msg in history:
        conversation.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    return conversation