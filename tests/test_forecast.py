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
from forecast import simulate_forecast


def get_data():
    return normalize_all(
        load_all()
    )


def test_forecast_builds():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    result = simulate_forecast(
        state,
        data
    )

    assert "timeline" in result

    assert (
        "minimum_projected_balance"
        in result
    )

    assert "is_safe" in result


def test_forecast_starts_at_current_balance():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    result = simulate_forecast(
        state,
        data
    )

    first = result[
        "timeline"
    ].iloc[0]

    assert (
        first["balance"]
        == state[
            "current_balance"
        ]
    )


def test_extra_payment_reduces_balance():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    normal = simulate_forecast(
        state,
        data
    )

    paid = simulate_forecast(
        state,
        data,
        extra_payments=[
            {
                "date":
                    state[
                        "request_date"
                    ],

                "amount":
                    Decimal("1000")
            }
        ]
    )

    assert (
        paid[
            "minimum_projected_balance"
        ]
        <=
        normal[
            "minimum_projected_balance"
        ]
    )


def test_all_requests_can_forecast():
    data = get_data()

    for request_id in (
        data["requests"][
            "request_id"
        ]
    ):

        state = build_financial_state(
            data,
            request_id
        )

        result = simulate_forecast(
            state,
            data
        )

        assert (
            result[
                "minimum_projected_balance"
            ]
            is not None
        )