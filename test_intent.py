from services.intent_service import extract_intent

while True:

    message = input("\nYou: ")

    if message.lower() == "exit":
        break

    intent = extract_intent(message)

    print("\nIntent:")
    print(intent)