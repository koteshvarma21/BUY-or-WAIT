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

REQUIRED_COLUMNS = {
    "financial_profiles": [
        "user_id",
        "home_currency",
        "current_available_balance",
        "minimum_balance_to_keep",
        "financial_priorities",
        "expense_categories_to_protect",
        "expense_categories_user_is_willing_to_reduce",
        "expense_categories_user_is_willing_to_stop",
        "payment_methods_user_will_consider",
        "max_installment_months",
    ],
    "financial_events": [
        "event_id",
        "user_id",
        "event_type",
        "description",
        "category",
        "direction",
        "amount",
        "currency",
        "event_date",
        "settlement_date",
        "status",
        "linked_event_id",
        "flexibility",
        "minimum_allowed_amount",
    ],
    "exchange_rates": [
        "rate_date",
        "from_currency",
        "to_currency",
        "rate",
    ],
    "requests": [
        "request_id",
        "user_id",
        "request_date",
        "request_type",
        "requested_amount",
        "desired_completion_date",
        "allows_partial_payment",
        "request_text",
    ],
    "sample_requests": [
        "request_id",
        "user_id",
        "request_date",
        "request_type",
        "requested_amount",
        "desired_completion_date",
        "allows_partial_payment",
        "request_text",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ],
    "request_payment_options": [
        "payment_option_id",
        "request_id",
        "payment_method",
        "payment_amount",
        "number_of_payments",
        "first_payment_date",
        "payment_frequency_days",
        "financing_fee",
        "total_payable_amount",
    ],
    "messages": [
        "message_id",
        "user_id",
        "request_id",
        "related_event_id",
        "sent_at",
        "source_type",
        "message_text",
    ],
    "images": [
        "image_id",
        "user_id",
        "request_id",
        "related_event_id",
    ],
    "output": [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ],
}


def validate_required_columns(name, df):
    required = REQUIRED_COLUMNS.get(name, [])
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"{FILES[name]} is missing required columns: "
            f"{', '.join(missing)}"
        )
    return missing


def load_csv(name):
    path = DATASET_DIR / FILES[name]

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    df = pd.read_csv(path)
    validate_required_columns(name, df)
    return df


def load_all():
    data = {}

    for name in FILES:
        data[name] = load_csv(name)

    return data