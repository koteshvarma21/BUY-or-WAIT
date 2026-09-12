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
from financial_state import (
    build_financial_state
)
from evidence import (
    apply_evidence
)
from forecast import (
    simulate_forecast
)


def get_data():
    return normalize_all(
        load_all()
    )


def get_state():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    return data, state


def first_event_id(state):
    return (
        state[
            "all_events"
        ]
        .iloc[0][
            "event_id"
        ]
    )


def test_linked_cancel_changes_status():
    data, state = get_state()

    event_id = first_event_id(
        state
    )

    facts = pd.DataFrame([
        {
            "message_id":
                state[
                    "messages"
                ].iloc[0][
                    "message_id"
                ],

            "fact_type":
                "cashflow_cancelled",

            "related_event_id":
                event_id,

            "amount":
                None,

            "currency":
                None,

            "date":
                None,

            "direction":
                None,

            "status":
                "cancelled",

            "category":
                None,

            "confidence":
                "high",

            "evidence_summary":
                "Transaction cancelled",
        }
    ])

    result = apply_evidence(
        state,
        message_facts=facts,
    )

    event = result[
        "all_events"
    ][
        result[
            "all_events"
        ][
            "event_id"
        ]
        == event_id
    ].iloc[0]

    assert (
        event["status"]
        == "cancelled"
    )


def test_linked_amendment_changes_amount():
    data, state = get_state()

    event_id = first_event_id(
        state
    )

    facts = pd.DataFrame([
        {
            "message_id":
                state[
                    "messages"
                ].iloc[0][
                    "message_id"
                ],

            "fact_type":
                "cashflow_amendment",

            "related_event_id":
                event_id,

            "amount":
                12345,

            "currency":
                state[
                    "home_currency"
                ],

            "date":
                None,

            "direction":
                None,

            "status":
                "scheduled",

            "category":
                None,

            "replaces_prior":
                True,

            "confidence":
                "high",

            "evidence_summary":
                "Amount changed",
        }
    ])

    result = apply_evidence(
        state,
        message_facts=facts,
    )

    event = result[
        "all_events"
    ][
        result[
            "all_events"
        ][
            "event_id"
        ]
        == event_id
    ].iloc[0]

    assert float(
        event["amount"]
    ) == 12345.0


def test_unlinked_high_confidence_creates_event():
    data, state = get_state()

    message_id = (
        state[
            "messages"
        ].iloc[0][
            "message_id"
        ]
    )

    date = (
        state[
            "request_date"
        ]
        + pd.Timedelta(
            days=5
        )
    )

    facts = pd.DataFrame([
        {
            "message_id":
                message_id,

            "fact_type":
                "cashflow_confirmed",

            "related_event_id":
                None,

            "amount":
                500,

            "currency":
                state[
                    "home_currency"
                ],

            "date":
                date,

            "direction":
                "credit",

            "status":
                "scheduled",

            "category":
                "salary",

            "confidence":
                "high",

            "evidence_summary":
                "Confirmed income",
        }
    ])

    before = len(
        state[
            "all_events"
        ]
    )

    result = apply_evidence(
        state,
        message_facts=facts,
    )

    after = len(
        result[
            "all_events"
        ]
    )

    assert after == before + 1


def test_low_confidence_does_not_change_money():
    data, state = get_state()

    message_id = (
        state[
            "messages"
        ].iloc[0][
            "message_id"
        ]
    )

    facts = pd.DataFrame([
        {
            "message_id":
                message_id,

            "fact_type":
                "cashflow_confirmed",

            "related_event_id":
                None,

            "amount":
                999999,

            "currency":
                state[
                    "home_currency"
                ],

            "date":
                state[
                    "request_date"
                ],

            "direction":
                "credit",

            "status":
                "scheduled",

            "category":
                "salary",

            "confidence":
                "low",

            "evidence_summary":
                "Uncertain",
        }
    ])

    before = len(
        state[
            "all_events"
        ]
    )

    result = apply_evidence(
        state,
        message_facts=facts,
    )

    assert len(
        result[
            "all_events"
        ]
    ) == before


def test_internal_transfer_is_ignored():
    data, state = get_state()

    message_id = (
        state[
            "messages"
        ].iloc[0][
            "message_id"
        ]
    )

    facts = pd.DataFrame([
        {
            "message_id":
                message_id,

            "fact_type":
                "internal_transfer",

            "related_event_id":
                None,

            "amount":
                1000,

            "currency":
                state[
                    "home_currency"
                ],

            "date":
                state[
                    "request_date"
                ],

            "direction":
                "credit",

            "status":
                "settled",

            "category":
                "transfer",

            "confidence":
                "high",

            "evidence_summary":
                "Internal transfer",
        }
    ])

    before = len(
        state[
            "all_events"
        ]
    )

    result = apply_evidence(
        state,
        message_facts=facts,
    )

    assert len(
        result[
            "all_events"
        ]
    ) == before


def test_irrelevant_message_is_ignored():
    data, state = get_state()

    facts = pd.DataFrame([
        {
            "message_id":
                "message_not_related",

            "fact_type":
                "cashflow_confirmed",

            "related_event_id":
                None,

            "amount":
                999,

            "currency":
                state[
                    "home_currency"
                ],

            "date":
                state[
                    "request_date"
                ],

            "direction":
                "credit",

            "status":
                "scheduled",

            "category":
                "salary",

            "confidence":
                "high",

            "evidence_summary":
                "Unrelated",
        }
    ])

    before = len(
        state[
            "all_events"
        ]
    )

    result = apply_evidence(
        state,
        message_facts=facts,
    )

    assert len(
        result[
            "all_events"
        ]
    ) == before


def test_forecast_runs_after_evidence():
    data, state = get_state()

    result = apply_evidence(
        state
    )

    forecast = simulate_forecast(
        result,
        data
    )

    assert (
        forecast[
            "minimum_projected_balance"
        ]
        is not None
    )