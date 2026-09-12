from copy import deepcopy
from decimal import Decimal

import pandas as pd

from financial_state import split_events


ACTIONABLE_TYPES = {
    "cashflow_confirmed",
    "cashflow_pending",
    "cashflow_cancelled",
    "cashflow_failed",
    "cashflow_amendment",
    "recurring_amount_change",
    "recurring_date_change",
    "refund_pending",
    "refund_settled",
    "invoice_due",
    "receipt_paid",
    "bill_due",
}


NON_CASH_TYPES = {
    "statement_balance",
    "internal_transfer",
    "non_cash_unrealized",
    "other",
}


def clean(value):
    if value is None:
        return None

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def money(value):
    if value is None or pd.isna(value):
        return None

    return Decimal(str(value))


def relevant_message_ids(state):
    messages = state.get(
        "messages"
    )

    if messages is None or messages.empty:
        return set()

    return set(
        messages[
            "message_id"
        ]
        .dropna()
        .tolist()
    )


def relevant_image_ids(state):
    images = state.get(
        "images"
    )

    if images is None or images.empty:
        return set()

    return set(
        images[
            "image_id"
        ]
        .dropna()
        .tolist()
    )


def prepare_message_facts(
    state,
    facts
):
    if (
        facts is None
        or facts.empty
    ):
        return pd.DataFrame()

    ids = relevant_message_ids(
        state
    )

    if not ids:
        return pd.DataFrame()

    rows = facts[
        facts["message_id"].isin(
            ids
        )
    ].copy()

    if rows.empty:
        return rows

    rows[
        "evidence_source"
    ] = "message"

    rows[
        "evidence_source_id"
    ] = rows[
        "message_id"
    ]

    messages = state[
        "messages"
    ][
        [
            "message_id",
            "sent_at",
        ]
    ].copy()

    rows = rows.merge(
        messages,
        on="message_id",
        how="left",
    )

    rows[
        "evidence_time"
    ] = rows[
        "sent_at"
    ]

    return rows


def prepare_image_facts(
    state,
    facts
):
    if (
        facts is None
        or facts.empty
    ):
        return pd.DataFrame()

    ids = relevant_image_ids(
        state
    )

    if not ids:
        return pd.DataFrame()

    rows = facts[
        facts["image_id"].isin(
            ids
        )
    ].copy()

    if rows.empty:
        return rows

    rows[
        "evidence_source"
    ] = "image"

    rows[
        "evidence_source_id"
    ] = rows[
        "image_id"
    ]

    rows[
        "evidence_time"
    ] = state[
        "request_date"
    ]

    return rows


def combine_evidence(
    state,
    message_facts=None,
    image_facts=None,
):
    frames = []

    msg = prepare_message_facts(
        state,
        message_facts,
    )

    if not msg.empty:
        frames.append(
            msg
        )

    img = prepare_image_facts(
        state,
        image_facts,
    )

    if not img.empty:
        frames.append(
            img
        )

    if not frames:
        return pd.DataFrame()

    result = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    if (
        "confidence"
        not in result.columns
    ):
        result[
            "confidence"
        ] = "low"

    result[
        "confidence"
    ] = (
        result[
            "confidence"
        ]
        .fillna("low")
        .astype(str)
        .str.lower()
    )

    result[
        "fact_type"
    ] = (
        result[
            "fact_type"
        ]
        .fillna("other")
        .astype(str)
        .str.lower()
    )

    result[
        "evidence_time"
    ] = pd.to_datetime(
        result[
            "evidence_time"
        ],
        errors="coerce",
    )

    result = result.sort_values(
        [
            "evidence_time",
            "evidence_source",
            "evidence_source_id",
        ],
        na_position="first",
    ).reset_index(
        drop=True
    )

    return result


def fact_is_actionable(
    fact
):
    confidence = str(
        fact.get(
            "confidence",
            "low"
        )
    ).lower()

    # Only high-confidence evidence is
    # allowed to change the money model.
    if confidence != "high":
        return False

    fact_type = str(
        fact.get(
            "fact_type",
            "other"
        )
    ).lower()

    if fact_type in NON_CASH_TYPES:
        return False

    return (
        fact_type
        in ACTIONABLE_TYPES
    )


def fact_date(fact):
    value = fact.get(
        "date"
    )

    if value is None or pd.isna(
        value
    ):
        return None

    return pd.Timestamp(
        value
    ).normalize()


def fact_status(fact):
    fact_type = str(
        fact.get(
            "fact_type",
            ""
        )
    ).lower()

    status = clean(
        fact.get(
            "status"
        )
    )

    if status is not None:
        status = status.lower()

    if fact_type == "cashflow_cancelled":
        return "cancelled"

    if fact_type == "cashflow_failed":
        return "failed"

    if fact_type == "refund_pending":
        return "pending"

    if fact_type == "refund_settled":
        return "settled"

    if fact_type in {
        "invoice_due",
        "bill_due",
    }:
        return (
            status
            or "scheduled"
        )

    if fact_type == "receipt_paid":
        return (
            status
            or "settled"
        )

    return status


def update_existing_event(
    events,
    index,
    fact,
):
    fact_type = str(
        fact.get(
            "fact_type",
            ""
        )
    ).lower()

    status = fact_status(
        fact
    )

    if status is not None:
        events.at[
            index,
            "status"
        ] = status

    amount = money(
        fact.get(
            "amount"
        )
    )

    replaces = bool(
        fact.get(
            "replaces_prior",
            False
        )
    )

    if (
        amount is not None
        and (
            replaces
            or fact_type
            in {
                "cashflow_amendment",
                "recurring_amount_change",
                "cashflow_confirmed",
                "refund_settled",
                "receipt_paid",
                "invoice_due",
                "bill_due",
            }
        )
    ):
        events.at[
            index,
            "amount"
        ] = float(
            amount
        )

    currency = clean(
        fact.get(
            "currency"
        )
    )

    if (
        currency is not None
        and amount is not None
    ):
        events.at[
            index,
            "currency"
        ] = currency.upper()

    date = fact_date(
        fact
    )

    if (
        date is not None
        and (
            replaces
            or fact_type
            in {
                "cashflow_amendment",
                "recurring_date_change",
                "cashflow_confirmed",
                "cashflow_pending",
                "refund_pending",
                "refund_settled",
                "invoice_due",
                "bill_due",
            }
        )
    ):
        events.at[
            index,
            "settlement_date"
        ] = date

    direction = clean(
        fact.get(
            "direction"
        )
    )

    if direction is not None:
        events.at[
            index,
            "direction"
        ] = direction.lower()

    category = clean(
        fact.get(
            "category"
        )
    )

    if category is not None:
        events.at[
            index,
            "category"
        ] = category.lower()

    summary = clean(
        fact.get(
            "evidence_summary"
        )
    )

    if (
        summary is not None
        and "description"
        in events.columns
    ):
        events.at[
            index,
            "description"
        ] = summary

    return events


def synthetic_event_id(
    fact,
    number
):
    source = clean(
        fact.get(
            "evidence_source"
        )
    ) or "evidence"

    source_id = clean(
        fact.get(
            "evidence_source_id"
        )
    ) or "unknown"

    return (
        f"evidence_"
        f"{source}_"
        f"{source_id}_"
        f"{number}"
    )


def can_create_synthetic_event(
    fact
):
    if not fact_is_actionable(
        fact
    ):
        return False

    fact_type = str(
        fact.get(
            "fact_type",
            ""
        )
    ).lower()

    if fact_type in {
        "cashflow_cancelled",
        "cashflow_failed",
        "recurring_amount_change",
        "recurring_date_change",
        "cashflow_amendment",
    }:
        # These normally need an existing
        # linked event.
        return False

    if fact_date(
        fact
    ) is None:
        return False

    if money(
        fact.get(
            "amount"
        )
    ) is None:
        return False

    direction = clean(
        fact.get(
            "direction"
        )
    )

    if direction not in {
        "credit",
        "debit",
    }:
        return False

    return True


def make_synthetic_event(
    events,
    state,
    fact,
    number,
):
    row = {
        column: None
        for column
        in events.columns
    }

    date = fact_date(
        fact
    )

    row[
        "event_id"
    ] = synthetic_event_id(
        fact,
        number,
    )

    row[
        "user_id"
    ] = state[
        "user_id"
    ]

    if (
        "event_date"
        in row
    ):
        row[
            "event_date"
        ] = date

    if (
        "settlement_date"
        in row
    ):
        row[
            "settlement_date"
        ] = date

    if (
        "event_type"
        in row
    ):
        row[
            "event_type"
        ] = "evidence"

    if (
        "category"
        in row
    ):
        row[
            "category"
        ] = (
            clean(
                fact.get(
                    "category"
                )
            )
            or "other"
        )

    if (
        "flexibility"
        in row
    ):
        row[
            "flexibility"
        ] = "fixed"

    if (
        "status"
        in row
    ):
        row[
            "status"
        ] = (
            fact_status(
                fact
            )
            or "scheduled"
        )

    if (
        "direction"
        in row
    ):
        row[
            "direction"
        ] = clean(
            fact.get(
                "direction"
            )
        )

    if (
        "amount"
        in row
    ):
        row[
            "amount"
        ] = float(
            money(
                fact.get(
                    "amount"
                )
            )
        )

    if (
        "currency"
        in row
    ):
        currency = clean(
            fact.get(
                "currency"
            )
        )

        row[
            "currency"
        ] = (
            currency.upper()
            if currency
            else state[
                "home_currency"
            ]
        )

    if (
        "description"
        in row
    ):
        row[
            "description"
        ] = (
            clean(
                fact.get(
                    "evidence_summary"
                )
            )
            or "Evidence-derived cashflow"
        )

    if (
        "linked_event_id"
        in row
    ):
        row[
            "linked_event_id"
        ] = clean(
            fact.get(
                "related_event_id"
            )
        )

    return row


def synthetic_key(
    fact
):
    date = fact_date(
        fact
    )

    amount = money(
        fact.get(
            "amount"
        )
    )

    return (
        date,
        amount,
        clean(
            fact.get(
                "currency"
            )
        ),
        clean(
            fact.get(
                "direction"
            )
        ),
        clean(
            fact.get(
                "category"
            )
        ),
        fact_status(
            fact
        ),
    )


def apply_evidence(
    state,
    message_facts=None,
    image_facts=None,
):
    new_state = deepcopy(
        state
    )

    events = (
        state[
            "all_events"
        ]
        .copy(
            deep=True
        )
    )

    evidence = combine_evidence(
        state,
        message_facts=
            message_facts,
        image_facts=
            image_facts,
    )

    applied = []
    ignored = []

    synthetic_seen = set()
    synthetic_rows = []

    for number, fact in evidence.iterrows():

        if not fact_is_actionable(
            fact
        ):
            ignored.append({
                "source":
                    fact.get(
                        "evidence_source"
                    ),
                "source_id":
                    fact.get(
                        "evidence_source_id"
                    ),
                "reason":
                    "not_high_confidence_or_not_cash",
            })
            continue

        related_event_id = clean(
            fact.get(
                "related_event_id"
            )
        )

        if related_event_id is not None:
            match = events[
                events[
                    "event_id"
                ]
                == related_event_id
            ]

            if not match.empty:
                for index in match.index:
                    events = update_existing_event(
                        events,
                        index,
                        fact,
                    )

                applied.append({
                    "source":
                        fact.get(
                            "evidence_source"
                        ),
                    "source_id":
                        fact.get(
                            "evidence_source_id"
                        ),
                    "action":
                        "updated_existing_event",
                    "event_id":
                        related_event_id,
                })

                continue

        if can_create_synthetic_event(
            fact
        ):
            key = synthetic_key(
                fact
            )

            if key in synthetic_seen:
                ignored.append({
                    "source":
                        fact.get(
                            "evidence_source"
                        ),
                    "source_id":
                        fact.get(
                            "evidence_source_id"
                        ),
                    "reason":
                        "duplicate_synthetic_cashflow",
                })
                continue

            synthetic_seen.add(
                key
            )

            row = make_synthetic_event(
                events,
                state,
                fact,
                number,
            )

            synthetic_rows.append(
                row
            )

            applied.append({
                "source":
                    fact.get(
                        "evidence_source"
                    ),
                "source_id":
                    fact.get(
                        "evidence_source_id"
                    ),
                "action":
                    "created_synthetic_event",
                "event_id":
                    row[
                        "event_id"
                    ],
            })

        else:
            ignored.append({
                "source":
                    fact.get(
                        "evidence_source"
                    ),
                "source_id":
                    fact.get(
                        "evidence_source_id"
                    ),
                "reason":
                    "insufficient_or_unlinked_evidence",
            })

    if synthetic_rows:
        synthetic_df = pd.DataFrame(
            synthetic_rows,
            columns=events.columns,
        )

        events = pd.concat(
            [
                events,
                synthetic_df,
            ],
            ignore_index=True,
        )

    if (
        "event_date"
        in events.columns
    ):
        events[
            "event_date"
        ] = pd.to_datetime(
            events[
                "event_date"
            ],
            errors="coerce",
        )

    if (
        "settlement_date"
        in events.columns
    ):
        events[
            "settlement_date"
        ] = pd.to_datetime(
            events[
                "settlement_date"
            ],
            errors="coerce",
        )

    events = events.sort_values(
        [
            "event_date",
            "settlement_date",
        ],
        na_position="last",
    ).reset_index(
        drop=True
    )

    (
        past_events,
        forecast_events,
    ) = split_events(
        events,
        state[
            "request_date"
        ],
        state[
            "forecast_end"
        ],
    )

    new_state[
        "all_events"
    ] = events

    new_state[
        "past_events"
    ] = past_events

    new_state[
        "forecast_events"
    ] = forecast_events

    new_state[
        "evidence_facts"
    ] = evidence

    new_state[
        "evidence_applied"
    ] = applied

    new_state[
        "evidence_ignored"
    ] = ignored

    return new_state