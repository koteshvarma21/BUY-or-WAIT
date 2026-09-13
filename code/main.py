import os
from pathlib import Path

import pandas as pd

from loader import load_all
from normalizer import normalize_all
from financial_state import build_financial_state
from message_parser import parse_all_messages, flatten_message_facts
from image_parser import parse_all_images, flatten_image_facts
from evidence import apply_evidence
from ranker import generate_ranked_decision
from explanation import attach_explanation
from validator import require_valid_decision


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "output.csv"


MESSAGE_FACT_COLUMNS = [
    "message_id",
    "fact_type",
    "related_event_id",
    "amount",
    "currency",
    "date",
    "direction",
    "status",
    "category",
    "recurrence",
    "relative_change_percent",
    "replaces_prior",
    "confidence",
    "evidence_summary",
]

IMAGE_FACT_COLUMNS = [
    "image_id",
    "document_type",
    "fact_type",
    "related_event_id",
    "amount",
    "currency",
    "date",
    "direction",
    "status",
    "category",
    "replaces_prior",
    "confidence",
    "evidence_summary",
]


def has_message_model_config():
    """Return True only when the message parser has every required model setting."""
    return (
        bool(os.getenv("LLM_BASE_URL"))
        and bool(os.getenv("LLM_API_KEY"))
        and bool(os.getenv("LLM_MODEL"))
    )


def has_image_model_config():
    """Return True only when the image parser has every required model setting."""
    return (
        bool(os.getenv("LLM_BASE_URL"))
        and bool(os.getenv("LLM_API_KEY"))
        and (bool(os.getenv("VISION_MODEL")) or bool(os.getenv("LLM_MODEL")))
    )


def empty_message_facts():
    return pd.DataFrame(columns=MESSAGE_FACT_COLUMNS)


def empty_image_facts():
    return pd.DataFrame(columns=IMAGE_FACT_COLUMNS)


def parse_messages_if_config(data):
    if not has_message_model_config():
        return empty_message_facts(), {"model_calls": 0}

    parsed, usage = parse_all_messages(data["messages"])
    return flatten_message_facts(parsed), usage


def parse_images_if_config(data):
    if not has_image_model_config():
        return empty_image_facts(), {"model_calls": 0}

    parsed, usage = parse_all_images(data["images"])
    return flatten_image_facts(parsed), usage


def build_output_row(decision):
    return {
        "request_id": decision["request_id"],
        "amount_safe_to_pay": decision["amount_safe_to_pay"],
        "affordability_status": decision["affordability_status"],
        "recommended_payment_method": decision["recommended_payment_method"],
        "payment_plan": decision["payment_plan"],
        "earliest_date_for_full_payment": decision["earliest_date_for_full_payment"],
        "spending_changes_needed": decision["spending_changes_needed"],
        "decision_explanation": decision["decision_explanation"],
    }


def run_pipeline():
    print("Loading and normalizing dataset...")
    data = load_all()
    data = normalize_all(data)

    message_facts, _ = parse_messages_if_config(data)
    image_facts, _ = parse_images_if_config(data)

    print("Generating final decisions...")
    rows = []
    for _, request in data["requests"].iterrows():
        request_id = request["request_id"]
        state = build_financial_state(data, request_id)
        state = apply_evidence(state, message_facts=message_facts, image_facts=image_facts)
        decision = generate_ranked_decision(state, data)
        decision = attach_explanation(state, decision)
        decision = require_valid_decision(state, data, decision)
        rows.append(build_output_row(decision))

    output = pd.DataFrame(rows, columns=[
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ])

    output.to_csv(OUTPUT_PATH, index=False)

    print(f"Wrote {OUTPUT_PATH}")
    print(f"Generated {len(output)} rows for {len(data['requests'])} official requests.")

    return output


def main():
    run_pipeline()


if __name__ == "__main__":
    main()
