import sys
from pathlib import Path

import pandas as pd


ROOT = Path(
    __file__
).resolve().parent.parent

CODE = ROOT / "code"

sys.path.insert(
    0,
    str(CODE)
)


from loader import load_all
from normalizer import normalize_all
from message_parser import (
    extract_json,
    flatten_message_facts,
    normalize_fact,
    parse_all_messages,
    parse_message_batch,
)


def get_data():
    return normalize_all(
        load_all()
    )


def fake_model(rows):
    items = []

    for _, row in rows.iterrows():
        items.append({
            "message_id":
                row["message_id"],

            "facts": [
                {
                    "fact_type":
                        "cashflow_pending",

                    "related_event_id":
                        (
                            None
                            if pd.isna(
                                row[
                                    "related_event_id"
                                ]
                            )
                            else row[
                                "related_event_id"
                            ]
                        ),

                    "amount":
                        None,

                    "currency":
                        None,

                    "date":
                        None,

                    "direction":
                        "credit",

                    "status":
                        "pending",

                    "category":
                        None,

                    "recurrence":
                        None,

                    "relative_change_percent":
                        None,

                    "replaces_prior":
                        False,

                    "confidence":
                        "high",

                    "evidence_summary":
                        "Test fact",
                }
            ],
        })

    return (
        {
            "items":
                items
        },
        {
            "prompt_tokens":
                100,

            "completion_tokens":
                40,

            "total_tokens":
                140,
        },
    )


def test_extract_json_plain():
    data = extract_json(
        '{"items":[]}'
    )

    assert data == {
        "items": []
    }


def test_extract_json_code_fence():
    data = extract_json(
        "```json\n"
        '{"items":[]}'
        "\n```"
    )

    assert data == {
        "items": []
    }


def test_normalize_fact():
    result = normalize_fact(
        {
            "fact_type":
                "CASHFLOW_CONFIRMED",

            "amount":
                "42,750,000",

            "currency":
                "idr",

            "date":
                "2025-08-15",

            "direction":
                "CREDIT",

            "status":
                "SCHEDULED",

            "recurrence":
                "MONTHLY",

            "confidence":
                "HIGH",
        },
        "message_01",
    )

    assert (
        result["fact_type"]
        == "cashflow_confirmed"
    )

    assert (
        result["amount"]
        == 42750000.0
    )

    assert (
        result["currency"]
        == "IDR"
    )

    assert (
        result["date"]
        == "2025-08-15"
    )

    assert (
        result["direction"]
        == "credit"
    )


def test_related_event_is_preserved():
    result = normalize_fact(
        {
            "fact_type":
                "cashflow_amendment",

            "related_event_id":
                None,
        },
        "message_10",
        "event_100",
    )

    assert (
        result[
            "related_event_id"
        ]
        == "event_100"
    )


def test_parse_batch_without_network():
    data = get_data()

    messages = data[
        "messages"
    ].head(3)

    result, usage = (
        parse_message_batch(
            messages,
            model_caller=
                fake_model,
        )
    )

    assert len(result) == 3

    assert (
        usage["total_tokens"]
        == 140
    )


def test_parse_all_messages_batches():
    data = get_data()

    messages = data[
        "messages"
    ].head(5)

    result, usage = (
        parse_all_messages(
            messages,
            batch_size=2,
            model_caller=
                fake_model,
        )
    )

    assert len(result) == 5

    assert (
        usage["model_calls"]
        == 3
    )

    assert (
        usage["total_tokens"]
        == 420
    )


def test_flatten_message_facts():
    parsed = [
        {
            "message_id":
                "message_01",

            "facts": [
                {
                    "message_id":
                        "message_01",

                    "fact_type":
                        "cashflow_confirmed",

                    "related_event_id":
                        None,

                    "amount":
                        1000,

                    "currency":
                        "INR",

                    "date":
                        "2026-01-01",

                    "direction":
                        "credit",

                    "status":
                        "scheduled",

                    "category":
                        "salary",

                    "recurrence":
                        "monthly",

                    "relative_change_percent":
                        None,

                    "replaces_prior":
                        False,

                    "confidence":
                        "high",

                    "evidence_summary":
                        "Confirmed salary",
                }
            ],
        }
    ]

    df = flatten_message_facts(
        parsed
    )

    assert len(df) == 1

    assert (
        df.iloc[0][
            "fact_type"
        ]
        == "cashflow_confirmed"
    )

    assert pd.api.types.is_datetime64_any_dtype(
        df["date"]
    )


def test_official_message_count():
    data = get_data()

    assert (
        len(
            data["messages"]
        )
        == 215
    )