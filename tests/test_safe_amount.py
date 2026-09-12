import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"

sys.path.insert(
    0,
    str(CODE)
)

from loader import load_all
from normalizer import normalize_all
from financial_state import build_financial_state
from safe_amount import calculate_safe_amount


def get_data():
    return normalize_all(
        load_all()
    )


def test_safe_amount_is_non_negative():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    result = calculate_safe_amount(
        state,
        data
    )

    assert (
        result["amount_safe_to_pay"]
        >= Decimal("0")
    )


def test_safe_amount_not_above_request():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    result = calculate_safe_amount(
        state,
        data
    )

    assert (
        result["amount_safe_to_pay"]
        <= state["requested_amount"]
    )


def test_safe_amount_keeps_balance_safe():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    result = calculate_safe_amount(
        state,
        data
    )

    safe = result[
        "amount_safe_to_pay"
    ]

    if safe > Decimal("0"):
        payment_forecast = result[
            "payment_forecast"
        ]

        assert (
            payment_forecast[
                "minimum_projected_balance"
            ]
            >=
            state["minimum_balance"]
        )


def test_unsafe_opening_balance_gives_zero():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    state["current_balance"] = (
        state["minimum_balance"]
        - Decimal("1")
    )

    result = calculate_safe_amount(
        state,
        data
    )

    assert (
        result["amount_safe_to_pay"]
        == Decimal("0")
    )


def test_all_requests_safe_amount():
    data = get_data()

    for request_id in (
        data["requests"]["request_id"]
    ):

        state = build_financial_state(
            data,
            request_id
        )

        result = calculate_safe_amount(
            state,
            data
        )

        safe = result[
            "amount_safe_to_pay"
        ]

        assert safe >= Decimal("0")

        assert (
            safe
            <= state[
                "requested_amount"
            ]
        )