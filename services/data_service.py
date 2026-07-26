import requests

JSON_URL = "https://farazajmal.github.io/gp-ultrahub-availability/availability.json"
SERVICES_JSON_URL = "https://farazajmal.github.io/gp-ultrahub-availability/services.json"


def load_data():
    response = requests.get(JSON_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def load_services_data():
    response = requests.get(SERVICES_JSON_URL, timeout=10)
    response.raise_for_status()
    return response.json()
