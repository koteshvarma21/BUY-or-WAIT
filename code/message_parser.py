import json
import os
from pathlib import Path

import pandas as pd
import requests


BASE_DIR = Path(
    __file__
).resolve().parent.parent

PROMPT_PATH = (
    BASE_DIR
    / "prompts"
    / "message_extraction.txt"
)


VALID_FACT_TYPES = {
    "cashflow_confirmed",
    "cashflow_pending",
    "cashflow_cancelled",
    "cashflow_failed",
    "cashflow_amendment",
    "recurring_amount_change",
    "recurring_date_change",
    "internal_transfer",
    "non_cash_unrealized",
    "refund_pending",
    "refund_settled",
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


VALID_RECURRENCES = {
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "one_time",
    "unknown",
    None,
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

    text = str(value).strip()

    if text == "":
        return None

    return text


def load_prompt():
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Missing prompt file: "
            f"{PROMPT_PATH}"
        )

    return PROMPT_PATH.read_text(
        encoding="utf-8"
    )


def message_to_dict(row):
    return {
        "message_id":
            clean_optional(
                row.get(
                    "message_id"
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

        "sent_at":
            (
                pd.Timestamp(
                    row["sent_at"]
                ).isoformat()
                if not pd.isna(
                    row.get(
                        "sent_at"
                    )
                )
                else None
            ),

        "source_type":
            clean_optional(
                row.get(
                    "source_type"
                )
            ),

        "message_text":
            clean_optional(
                row.get(
                    "message_text"
                )
            ),
    }


def build_user_content(rows):
    messages = []

    for _, row in rows.iterrows():
        messages.append(
            message_to_dict(
                row
            )
        )

    return json.dumps(
        {
            "messages":
                messages
        },
        ensure_ascii=False,
        indent=2,
    )


def strip_code_fence(text):
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

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


def extract_json(text):
    text = strip_code_fence(
        text
    )

    try:
        return json.loads(
            text
        )

    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

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
                "Could not parse model "
                "response as JSON"
            ) from exc


def normalize_number(value):
    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):
        return value

    try:
        return float(
            str(value)
            .replace(",", "")
            .strip()
        )

    except (
        ValueError,
        TypeError,
    ):
        return None


def normalize_date(value):
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


def normalize_fact(
    fact,
    message_id,
    related_event_id=None
):
    fact_type = str(
        fact.get(
            "fact_type",
            "other"
        )
    ).lower()

    if fact_type not in VALID_FACT_TYPES:
        fact_type = "other"

    direction = fact.get(
        "direction"
    )

    if direction is not None:
        direction = str(
            direction
        ).lower()

    if direction not in VALID_DIRECTIONS:
        direction = None

    status = str(
        fact.get(
            "status",
            "unknown"
        )
    ).lower()

    if status not in VALID_STATUSES:
        status = "unknown"

    recurrence = fact.get(
        "recurrence"
    )

    if recurrence is not None:
        recurrence = str(
            recurrence
        ).lower()

    if (
        recurrence
        not in VALID_RECURRENCES
    ):
        recurrence = "unknown"

    confidence = str(
        fact.get(
            "confidence",
            "medium"
        )
    ).lower()

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
        currency = currency.upper()

    supplied_event = (
        clean_optional(
            fact.get(
                "related_event_id"
            )
        )
    )

    if supplied_event is None:
        supplied_event = (
            related_event_id
        )

    return {
        "message_id":
            message_id,

        "fact_type":
            fact_type,

        "related_event_id":
            supplied_event,

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

        "recurrence":
            recurrence,

        "relative_change_percent":
            normalize_number(
                fact.get(
                    "relative_change_percent"
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
    input_rows
):
    raw_items = response.get(
        "items",
        []
    )

    by_id = {}

    for item in raw_items:
        message_id = (
            clean_optional(
                item.get(
                    "message_id"
                )
            )
        )

        if message_id is None:
            continue

        by_id[message_id] = item

    result = []

    for _, row in input_rows.iterrows():
        message_id = clean_optional(
            row["message_id"]
        )

        related_event_id = (
            clean_optional(
                row.get(
                    "related_event_id"
                )
            )
        )

        item = by_id.get(
            message_id,
            {}
        )

        facts = item.get(
            "facts",
            []
        )

        normalized_facts = []

        for fact in facts:
            normalized_facts.append(
                normalize_fact(
                    fact,
                    message_id,
                    related_event_id,
                )
            )

        result.append({
            "message_id":
                message_id,

            "facts":
                normalized_facts,
        })

    return result


def get_llm_config():
    base_url = os.getenv(
        "LLM_BASE_URL"
    )

    api_key = os.getenv(
        "LLM_API_KEY"
    )

    model = os.getenv(
        "LLM_MODEL"
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
            "LLM_MODEL is not set"
        )

    return (
        base_url.rstrip("/"),
        api_key,
        model,
    )


def call_model(
    rows,
    timeout=90
):
    (
        base_url,
        api_key,
        model,
    ) = get_llm_config()

    prompt = load_prompt()

    payload = {
        "model":
            model,

        "temperature":
            0,

        "messages": [
            {
                "role":
                    "system",

                "content":
                    prompt,
            },
            {
                "role":
                    "user",

                "content":
                    build_user_content(
                        rows
                    ),
            },
        ],
    }

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

    response.raise_for_status()

    body = response.json()

    choices = body.get(
        "choices",
        []
    )

    if not choices:
        raise ValueError(
            "Model response has "
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
            "Model response content "
            "is empty"
        )

    parsed = extract_json(
        content
    )

    usage = body.get(
        "usage",
        {}
    )

    return parsed, usage


def parse_message_batch(
    rows,
    model_caller=None
):
    if rows.empty:
        return [], {}

    if model_caller is None:
        model_caller = call_model

    response, usage = (
        model_caller(
            rows
        )
    )

    parsed = normalize_result(
        response,
        rows
    )

    return parsed, usage


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


def parse_all_messages(
    messages,
    batch_size=20,
    model_caller=None
):
    if batch_size <= 0:
        raise ValueError(
            "batch_size must be positive"
        )

    messages = messages.sort_values(
        [
            "sent_at",
            "message_id",
        ]
    ).reset_index(
        drop=True
    )

    all_results = []

    usage_total = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model_calls": 0,
    }

    for start in range(
        0,
        len(messages),
        batch_size,
    ):
        batch = messages.iloc[
            start:start + batch_size
        ]

        result, usage = (
            parse_message_batch(
                batch,
                model_caller=
                    model_caller,
            )
        )

        all_results.extend(
            result
        )

        merge_usage(
            usage_total,
            usage
        )

        usage_total[
            "model_calls"
        ] += 1

    return (
        all_results,
        usage_total,
    )


def flatten_message_facts(
    parsed_messages
):
    rows = []

    for item in parsed_messages:
        for fact in item.get(
            "facts",
            []
        ):
            rows.append(
                fact
            )

    if not rows:
        return pd.DataFrame(
            columns=[
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
        )

    df = pd.DataFrame(
        rows
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    return df