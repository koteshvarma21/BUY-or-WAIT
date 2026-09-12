from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset"

FILES = {
    "financial_profiles": "financial_profiles.csv",
    "financial_events": "financial_events.csv",
    "exchange_rates": "exchange_rates.csv",
    "requests": "requests.csv",
    "sample_requests": "sample_requests.csv",
    "request_payment_options": "request_payment_options.csv",
    "messages": "messages.csv",
    "images": "images.csv",
    "output": "output.csv",
}


def load_csv(name):
    path = DATASET_DIR / FILES[name]

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    return pd.read_csv(path)


def load_all():
    data = {}

    for name in FILES:
        data[name] = load_csv(name)

    return data