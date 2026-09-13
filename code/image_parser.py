import base64
import json
import mimetypes
import os
import time
from pathlib import Path

import pandas as pd
import requests


BASE_DIR = Path(
    __file__
).resolve().parent.parent

IMAGE_DIR = (
    BASE_DIR
    / "dataset"
    / "media"
    / "images"
)

CACHE_DIR = BASE_DIR / ".image_cache"
CACHE_FILE = CACHE_DIR / "image_results.json"

PROMPT_PATH = (
    BASE_DIR
    / "prompts"
    / "image_extraction.txt"
)


VALID_DOCUMENT_TYPES = {
    "receipt",
    "invoice",
    "bill",
    "bank_statement",
    "account_statement",
    "order_summary",
    "payslip",
    "rent_receipt",
    "medical_bill",
    "utility_bill",
    "tax_document",
    "other",
}


VALID_FACT_TYPES = {
    "cashflow_confirmed",
    "cashflow_pending",
    "cashflow_cancelled",
    "cashflow_failed",
    "cashflow_amendment",
    "invoice_due",
    "receipt_paid",
    "bill_due",
    "statement_balance",
    "refund_pending",
    "refund_settled",
    "recurring_amount_change",
    "recurring_date_change",
    "internal_transfer",
    "non_cash_unrealized",
    "other",
}


VALID_DIRECTIONS = {
    "credit",
    "debit",
    None,
}


VALID_STATUSES = {
    "settled",
    "pending",
    "scheduled",
    "failed",
    "cancelled",
    "unrealized",
    "unknown",
}


VALID_CONFIDENCE = {
    "high",
    "medium",
    "low",
}


def clean_optional(value):
    if value is None:
        return None

    if pd.isna(value):
        return None

    value = str(
        value
    ).strip()

    if value == "":
        return None

    return value


def load_prompt():
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Missing prompt file: "
            f"{PROMPT_PATH}"
        )

    return PROMPT_PATH.read_text(
        encoding="utf-8"
    )


def get_image_path(
    image_id
):
    image_id = clean_optional(
        image_id
    )

    if image_id is None:
        raise ValueError(
            "image_id is missing"
        )

    path = (
        IMAGE_DIR
        / f"{image_id}.png"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Missing image file: "
            f"{path}"
        )

    return path


def image_to_base64(
    path
):
    path = Path(
        path
    )

    with path.open(
        "rb"
    ) as file:
        return base64.b64encode(
            file.read()
        ).decode(
            "ascii"
        )


def image_to_data_url(
    path
):
    path = Path(
        path
    )

    mime_type, _ = (
        mimetypes.guess_type(
            str(path)
        )
    )

    if mime_type is None:
        mime_type = (
            "image/png"
        )

    encoded = image_to_base64(
        path
    )

    return (
        f"data:{mime_type};"
        f"base64,{encoded}"
    )


def image_metadata(
    row
):
    return {
        "image_id":
            clean_optional(
                row.get(
                    "image_id"
                )
            ),

        "user_id":
            clean_optional(
                row.get(
                    "user_id"
                )
            ),

        "request_id":
            clean_optional(
                row.get(
                    "request_id"
                )
            ),

        "related_event_id":
            clean_optional(
                row.get(
                    "related_event_id"
                )
            ),
    }


def strip_code_fence(
    text
):
    text = text.strip()

    if text.startswith(
        "```"
    ):
        lines = (
            text.splitlines()
        )

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip()
            == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(
            lines
        ).strip()

    return text


def extract_json(
    text
):
    text = strip_code_fence(
        text
    )

    try:
        return json.loads(
            text
        )

    except json.JSONDecodeError:
        start = text.find(
            "{"
        )

        end = text.rfind(
            "}"
        )

        if (
            start == -1
            or end == -1
            or end < start
        ):
            raise ValueError(
                "Model response does not "
                "contain valid JSON"
            )

        candidate = text[
            start:end + 1
        ]

        try:
            return json.loads(
                candidate
            )

        except json.JSONDecodeError as exc:
            raise ValueError(
                "Could not parse image "
                "model response as JSON"
            ) from exc


def normalize_number(
    value
):
    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):
        return value

    text = str(
        value
    )

    text = (
        text.replace(
            ",",
            ""
        )
        .strip()
    )

    try:
        return float(
            text
        )

    except (
        ValueError,
        TypeError,
    ):
        return None


def normalize_date(
    value
):
    if value is None:
        return None

    try:
        date = pd.Timestamp(
            value
        )

    except Exception:
        return None

    return date.strftime(
        "%Y-%m-%d"
    )


def normalize_document_type(
    value
):
    if value is None:
        return "other"

    value = str(
        value
    ).strip().lower()

    if (
        value
        not in
        VALID_DOCUMENT_TYPES
    ):
        return "other"

    return value


def normalize_fact(
    fact,
    image_id,
    related_event_id=None
):
    fact_type = str(
        fact.get(
            "fact_type",
            "other"
        )
    ).strip().lower()

    if (
        fact_type
        not in VALID_FACT_TYPES
    ):
        fact_type = "other"

    direction = fact.get(
        "direction"
    )

    if direction is not None:
        direction = str(
            direction
        ).strip().lower()

    if (
        direction
        not in VALID_DIRECTIONS
    ):
        direction = None

    status = str(
        fact.get(
            "status",
            "unknown"
        )
    ).strip().lower()

    if (
        status
        not in VALID_STATUSES
    ):
        status = "unknown"

    confidence = str(
        fact.get(
            "confidence",
            "medium"
        )
    ).strip().lower()

    if (
        confidence
        not in VALID_CONFIDENCE
    ):
        confidence = "medium"

    currency = clean_optional(
        fact.get(
            "currency"
        )
    )

    if currency is not None:
        currency = (
            currency.upper()
        )

    event_id = clean_optional(
        fact.get(
            "related_event_id"
        )
    )

    if event_id is None:
        event_id = (
            related_event_id
        )

    return {
        "image_id":
            image_id,

        "fact_type":
            fact_type,

        "related_event_id":
            event_id,

        "amount":
            normalize_number(
                fact.get(
                    "amount"
                )
            ),

        "currency":
            currency,

        "date":
            normalize_date(
                fact.get(
                    "date"
                )
            ),

        "direction":
            direction,

        "status":
            status,

        "category":
            clean_optional(
                fact.get(
                    "category"
                )
            ),

        "replaces_prior":
            bool(
                fact.get(
                    "replaces_prior",
                    False
                )
            ),

        "confidence":
            confidence,

        "evidence_summary":
            clean_optional(
                fact.get(
                    "evidence_summary"
                )
            ),
    }


def normalize_result(
    response,
    row
):
    metadata = image_metadata(
        row
    )

    image_id = metadata[
        "image_id"
    ]

    related_event_id = (
        metadata[
            "related_event_id"
        ]
    )

    response_image_id = (
        clean_optional(
            response.get(
                "image_id"
            )
        )
    )

    if (
        response_image_id
        is not None
        and
        response_image_id
        != image_id
    ):
        response_image_id = (
            image_id
        )

    document_type = (
        normalize_document_type(
            response.get(
                "document_type"
            )
        )
    )

    raw_facts = response.get(
        "facts",
        []
    )

    if not isinstance(
        raw_facts,
        list
    ):
        raw_facts = []

    facts = []

    for fact in raw_facts:
        if not isinstance(
            fact,
            dict
        ):
            continue

        facts.append(
            normalize_fact(
                fact,
                image_id,
                related_event_id,
            )
        )

    return {
        "image_id":
            image_id,

        "user_id":
            metadata[
                "user_id"
            ],

        "request_id":
            metadata[
                "request_id"
            ],

        "related_event_id":
            related_event_id,

        "document_type":
            document_type,

        "facts":
            facts,
    }


def load_image_cache():
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not CACHE_FILE.exists():
        return {}

    try:
        data = json.loads(
            CACHE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}

    if not isinstance(
        data,
        dict,
    ):
        return {}

    return data


def save_image_cache(image_id, result, usage):
    if not image_id:
        return

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache = load_image_cache()
    cache[image_id] = {
        "result": result,
        "usage": usage or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

    CACHE_FILE.write_text(
        json.dumps(
            cache,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_llm_config():
    base_url = os.getenv(
        "LLM_BASE_URL"
    )

    api_key = os.getenv(
        "LLM_API_KEY"
    )

    model = (
        os.getenv(
            "VISION_MODEL"
        )
        or os.getenv(
            "LLM_MODEL"
        )
    )

    if not base_url:
        raise ValueError(
            "LLM_BASE_URL is not set"
        )

    if not api_key:
        raise ValueError(
            "LLM_API_KEY is not set"
        )

    if not model:
        raise ValueError(
            "VISION_MODEL or LLM_MODEL "
            "must be set"
        )

    return (
        base_url.rstrip(
            "/"
        ),
        api_key,
        model,
    )


def build_user_content(
    row
):
    metadata = (
        image_metadata(
            row
        )
    )

    return (
        "Extract financial facts "
        "from this document.\n\n"
        "Metadata:\n"
        + json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        )
    )


def call_model(
    row,
    timeout=90
):
    (
        base_url,
        api_key,
        model,
    ) = get_llm_config()

    image_id = clean_optional(
        row.get(
            "image_id"
        )
    )

    path = get_image_path(
        image_id
    )

    data_url = image_to_data_url(
        path
    )

    payload = {
        "model":
            model,

        "temperature":
            0,

        "response_format": {
            "type": "json_object"
        },

        "messages": [
            {
                "role":
                    "system",

                "content":
                    load_prompt(),
            },

            {
                "role":
                    "user",

                "content": [
                    {
                        "type":
                            "text",

                        "text":
                            build_user_content(
                                row
                            ),
                    },

                    {
                        "type":
                            "image_url",

                        "image_url": {
                            "url":
                                data_url
                        },
                    },
                ],
            },
        ],
    }

    response = None

    for attempt in range(6):
        response = requests.post(
            (
                base_url
                + "/chat/completions"
            ),
            headers={
                "Authorization":
                    f"Bearer {api_key}",

                "Content-Type":
                    "application/json",
            },
            json=payload,
            timeout=timeout,
        )

        if response.status_code == 429:
            retry_after = response.headers.get(
                "Retry-After"
            )
            delay = None

            try:
                delay = int(
                    retry_after
                )
            except Exception:
                delay = None

            if delay is None:
                try:
                    body = response.json()
                except Exception:
                    body = {}

                details = body.get("error", {}).get("details", []) or []
                for item in details:
                    if isinstance(item, dict) and item.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                        retry_delay = item.get("retryDelay")
                        if isinstance(retry_delay, str):
                            text = retry_delay.strip().lower()
                            if text.endswith("s"):
                                try:
                                    delay = int(float(text[:-1]))
                                except Exception:
                                    delay = None
                            else:
                                try:
                                    delay = int(float(text))
                                except Exception:
                                    delay = None
                            break

                if delay is None:
                    delay = 20 * (attempt + 1)

            delay = min(
                max(0, int(delay)),
                60,
            )

            print(
                f"Rate limited for {image_id}. "
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

            if attempt == 5:
                break

            continue

        break

    if response is None or response.status_code >= 400:
        raise RuntimeError(
            f"Gemini request failed "
            f"({getattr(response, 'status_code', 'unknown')}): "
            f"{getattr(response, 'text', '')}"
        )

    body = response.json()

    choices = body.get(
        "choices",
        []
    )

    if not choices:
        raise ValueError(
            "Vision model returned "
            "no choices"
        )

    content = (
        choices[0]
        .get(
            "message",
            {}
        )
        .get(
            "content"
        )
    )

    if not content:
        raise ValueError(
            "Vision model returned "
            "empty content"
        )

    parsed = extract_json(
        content
    )

    usage = body.get(
        "usage",
        {}
    )

    return (
        parsed,
        usage,
    )


def parse_image(
    row,
    model_caller=None
):
    if model_caller is None:
        model_caller = (
            call_model
        )

    response, usage = (
        model_caller(
            row
        )
    )

    result = normalize_result(
        response,
        row
    )

    return (
        result,
        usage,
    )


def merge_usage(
    total,
    usage
):
    for key in [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ]:
        value = usage.get(
            key,
            0
        )

        if value is None:
            value = 0

        total[key] = (
            total.get(
                key,
                0
            )
            + int(value)
        )

    return total


def parse_all_images(
    images,
    model_caller=None
):
    images = (
        images
        .sort_values(
            "image_id"
        )
        .reset_index(
            drop=True
        )
    )

    results = []

    usage_total = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model_calls": 0,
    }

    cache = load_image_cache()

    for index, row in images.iterrows():
        image_id = clean_optional(
            row.get(
                "image_id"
            )
        )

        if image_id in cache:
            result = cache[image_id].get(
                "result"
            )
            usage = cache[image_id].get(
                "usage",
                {},
            )
            if isinstance(result, dict):
                results.append(result)
                merge_usage(
                    usage_total,
                    usage,
                )
                usage_total[
                    "model_calls"
                ] += 1
                continue

        try:
            result, usage = (
                parse_image(
                    row,
                    model_caller=
                        model_caller,
                )
            )
        except Exception as exc:
            print(
                f"Skipping image {image_id} after parse failure: {exc}"
            )
            continue

        results.append(
            result
        )

        merge_usage(
            usage_total,
            usage
        )

        usage_total[
            "model_calls"
        ] += 1

        save_image_cache(
            image_id,
            result,
            usage,
        )

        if (
            model_caller is None
            and index < len(images) - 1
        ):
            time.sleep(20)

    return (
        results,
        usage_total,
    )


def flatten_image_facts(
    parsed_images
):
    rows = []

    for item in parsed_images:
        image_id = item.get(
            "image_id"
        )

        document_type = (
            item.get(
                "document_type",
                "other"
            )
        )

        for fact in item.get(
            "facts",
            []
        ):
            row = dict(
                fact
            )

            row[
                "image_id"
            ] = image_id

            row[
                "document_type"
            ] = (
                document_type
            )

            rows.append(
                row
            )

    columns = [
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

    if not rows:
        return pd.DataFrame(
            columns=columns
        )

    df = pd.DataFrame(
        rows
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    return df


def verify_image_files(
    images
):
    missing = []

    for image_id in images[
        "image_id"
    ]:
        try:
            get_image_path(
                image_id
            )

        except FileNotFoundError:
            missing.append(
                image_id
            )

    return missing