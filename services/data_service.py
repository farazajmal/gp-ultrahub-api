import os
import json
import requests

JSON_URL = "https://farazajmal.github.io/gp-ultrahub-availability/availability.json"
SERVICES_JSON_URL = "https://farazajmal.github.io/gp-ultrahub-availability/services.json"


def load_data():
    if os.path.exists("availability.json"):
        try:
            with open("availability.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    response = requests.get(JSON_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def load_services_data():
    if os.path.exists("services.json"):
        try:
            with open("services.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    response = requests.get(SERVICES_JSON_URL, timeout=10)
    response.raise_for_status()
    return response.json()

