import sys
from decimal import Decimal
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
from ranker import (
    choose_best_candidate,
    generate_ranked_decision,
    rank_plans,
)


def get_data():
    return normalize_all(
        load_all()
    )


def base_state():
    return {
        "request_id":
            "test_request",

        "desired_completion_date":
            pd.Timestamp(
                "2026-12-31"
            ),
    }


def candidate(
    method,
    total,
    start,
    end,
    count=1,
    spending="none",
):
    return {
        "recommended_payment_method":
            method,

        "affordability_status":
            "affordable_with_plan",

        "payment_plan":
            "test",

        "start_date":
            pd.Timestamp(start),

        "last_payment_date":
            pd.Timestamp(end),

        "number_of_payments":
            count,

        "total_payable_amount":
            Decimal(str(total)),

        "financing_fee":
            Decimal("0"),

        "payment_option_id":
            None,

        "spending_changes_needed":
            spending,
    }


def test_deadline_has_highest_priority():
    state = base_state()

    late = candidate(
        "full_payment",
        100,
        "2026-09-01",
        "2027-01-01",
    )

    on_time = candidate(
        "installments",
        120,
        "2026-09-01",
        "2026-12-01",
        count=3,
    )

    best = choose_best_candidate(
        [late, on_time],
        state
    )

    assert (
        best[
            "recommended_payment_method"
        ]
        == "installments"
    )


def test_no_spending_change_beats_change():
    state = base_state()

    changed = candidate(
        "full_payment",
        100,
        "2026-09-01",
        "2026-09-01",
        spending="reduce dining",
    )

    unchanged = candidate(
        "installments",
        110,
        "2026-09-01",
        "2026-12-01",
        count=3,
        spending="none",
    )

    best = choose_best_candidate(
        [changed, unchanged],
        state
    )

    assert (
        best[
            "recommended_payment_method"
        ]
        == "installments"
    )


def test_lower_total_cost_wins():
    state = base_state()

    expensive = candidate(
        "installments",
        120,
        "2026-09-01",
        "2026-11-01",
        count=3,
    )

    cheap = candidate(
        "installments",
        105,
        "2026-09-01",
        "2026-11-01",
        count=3,
    )

    best = choose_best_candidate(
        [expensive, cheap],
        state
    )

    assert (
        best[
            "total_payable_amount"
        ]
        == Decimal("105")
    )


def test_earlier_start_wins_after_cost():
    state = base_state()

    later = candidate(
        "wait",
        100,
        "2026-10-01",
        "2026-10-01",
    )

    earlier = candidate(
        "full_payment",
        100,
        "2026-09-01",
        "2026-09-01",
    )

    best = choose_best_candidate(
        [later, earlier],
        state
    )

    assert (
        best[
            "recommended_payment_method"
        ]
        == "full_payment"
    )


def test_fewer_payments_wins_after_other_ties():
    state = base_state()

    many = candidate(
        "installments",
        100,
        "2026-09-01",
        "2026-12-01",
        count=4,
    )

    few = candidate(
        "installments",
        100,
        "2026-09-01",
        "2026-12-01",
        count=2,
    )

    best = choose_best_candidate(
        [many, few],
        state
    )

    assert (
        best[
            "number_of_payments"
        ]
        == 2
    )


def test_no_candidate_returns_not_affordable():
    state = {
        "request_id":
            "test_request",

        "desired_completion_date":
            pd.Timestamp(
                "2026-12-31"
            ),
    }

    plans = {
        "amount_safe_to_pay":
            Decimal("0"),

        "earliest_date_for_full_payment":
            None,

        "candidates":
            [],
    }

    result = rank_plans(
        state,
        plans
    )

    assert (
        result[
            "affordability_status"
        ]
        == "not_affordable"
    )

    assert (
        result[
            "recommended_payment_method"
        ]
        == "not_recommended"
    )

    assert (
        result["payment_plan"]
        == "none"
    )


def test_all_requests_get_ranked_decision():
    data = get_data()

    valid_statuses = {
        "affordable_now",
        "affordable_with_plan",
        "affordable_later",
        "not_affordable",
    }

    valid_methods = {
        "full_payment",
        "partial_payment",
        "installments",
        "wait",
        "not_recommended",
    }

    for request_id in (
        data["requests"][
            "request_id"
        ]
    ):

        state = build_financial_state(
            data,
            request_id
        )

        result = generate_ranked_decision(
            state,
            data
        )

        assert (
            result["request_id"]
            == request_id
        )

        assert (
            result[
                "affordability_status"
            ]
            in valid_statuses
        )

        assert (
            result[
                "recommended_payment_method"
            ]
            in valid_methods
        )

        assert (
            result[
                "amount_safe_to_pay"
            ]
            >= Decimal("0")
        )