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
from image_parser import (
    extract_json,
    flatten_image_facts,
    get_image_path,
    image_to_data_url,
    normalize_fact,
    parse_all_images,
    parse_image,
    verify_image_files,
)


def get_data():
    return normalize_all(
        load_all()
    )


def fake_model(row):
    return (
        {
            "image_id":
                row["image_id"],

            "document_type":
                "receipt",

            "facts": [
                {
                    "fact_type":
                        "receipt_paid",

                    "related_event_id":
                        None,

                    "amount":
                        "1,250.50",

                    "currency":
                        "inr",

                    "date":
                        "2026-09-10",

                    "direction":
                        "debit",

                    "status":
                        "settled",

                    "category":
                        "shopping",

                    "replaces_prior":
                        False,

                    "confidence":
                        "high",

                    "evidence_summary":
                        "Receipt shows payment.",
                }
            ],
        },

        {
            "prompt_tokens":
                100,

            "completion_tokens":
                50,

            "total_tokens":
                150,
        },
    )


def test_official_image_count():
    data = get_data()

    assert (
        len(
            data["images"]
        )
        == 16
    )


def test_all_official_image_files_exist():
    data = get_data()

    missing = verify_image_files(
        data["images"]
    )

    assert missing == []


def test_get_image_path():
    path = get_image_path(
        "image_06"
    )

    assert path.exists()

    assert (
        path.name
        == "image_06.png"
    )


def test_image_data_url():
    path = get_image_path(
        "image_06"
    )

    data_url = (
        image_to_data_url(
            path
        )
    )

    assert (
        data_url.startswith(
            "data:image/png;base64,"
        )
    )

    assert len(
        data_url
    ) > 100


def test_extract_json():
    result = extract_json(
        """
        ```json
        {
          "image_id": "image_01",
          "document_type": "receipt",
          "facts": []
        }
        ```
        """
    )

    assert (
        result[
            "image_id"
        ]
        == "image_01"
    )


def test_normalize_image_fact():
    result = normalize_fact(
        {
            "fact_type":
                "RECEIPT_PAID",

            "amount":
                "1,250.50",

            "currency":
                "inr",

            "date":
                "2026-09-10",

            "direction":
                "DEBIT",

            "status":
                "SETTLED",

            "confidence":
                "HIGH",
        },
        "image_01",
        "event_253",
    )

    assert (
        result["fact_type"]
        == "receipt_paid"
    )

    assert (
        result["amount"]
        == 1250.50
    )

    assert (
        result["currency"]
        == "INR"
    )

    assert (
        result[
            "related_event_id"
        ]
        == "event_253"
    )


def test_parse_image_without_network():
    data = get_data()

    row = data[
        "images"
    ].iloc[0]

    result, usage = (
        parse_image(
            row,
            model_caller=
                fake_model,
        )
    )

    assert (
        result[
            "image_id"
        ]
        == row[
            "image_id"
        ]
    )

    assert (
        len(
            result["facts"]
        )
        == 1
    )

    assert (
        result["facts"][0][
            "related_event_id"
        ]
        ==
        row[
            "related_event_id"
        ]
    )

    assert (
        usage[
            "total_tokens"
        ]
        == 150
    )


def test_parse_all_images_without_network():
    data = get_data()

    images = data[
        "images"
    ].head(3)

    results, usage = (
        parse_all_images(
            images,
            model_caller=
                fake_model,
        )
    )

    assert len(
        results
    ) == 3

    assert (
        usage[
            "model_calls"
        ]
        == 3
    )

    assert (
        usage[
            "total_tokens"
        ]
        == 450
    )


def test_flatten_image_facts():
    parsed = [
        {
            "image_id":
                "image_01",

            "document_type":
                "receipt",

            "facts": [
                {
                    "image_id":
                        "image_01",

                    "fact_type":
                        "receipt_paid",

                    "related_event_id":
                        "event_253",

                    "amount":
                        1000,

                    "currency":
                        "INR",

                    "date":
                        "2026-09-10",

                    "direction":
                        "debit",

                    "status":
                        "settled",

                    "category":
                        "shopping",

                    "replaces_prior":
                        False,

                    "confidence":
                        "high",

                    "evidence_summary":
                        "Paid receipt",
                }
            ],
        }
    ]

    df = flatten_image_facts(
        parsed
    )

    assert len(
        df
    ) == 1

    assert (
        df.iloc[0][
            "document_type"
        ]
        == "receipt"
    )

    assert (
        df.iloc[0][
            "fact_type"
        ]
        == "receipt_paid"
    )

    assert (
        pd.api.types
        .is_datetime64_any_dtype(
            df["date"]
        )
    )