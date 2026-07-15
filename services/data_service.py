import requests

JSON_URL = "https://farazajmal.github.io/gp-ultrahub-availability/availability.json"


def load_data():
    response = requests.get(JSON_URL, timeout=10)
    response.raise_for_status()
    return response.json()