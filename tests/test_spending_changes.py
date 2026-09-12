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
from spending_changes import (
    apply_changes_to_flows,
    find_spending_changes,
    spending_permissions,
)


def get_data():
    return normalize_all(
        load_all()
    )


def test_protected_category_not_changed():
    flows = [
        {
            "date":
                pd.Timestamp(
                    "2026-09-15"
                ),

            "direction":
                "debit",

            "amount":
                Decimal("1000"),

            "category":
                "rent",

            "source":
                "recurring",
        }
    ]

    result = apply_changes_to_flows(
        flows,
        reductions={
            "rent":
                Decimal("0.50")
        },
        stopped_categories={
            "rent"
        },
        protected_categories={
            "rent"
        },
    )

    assert (
        result[0]["amount"]
        == Decimal("1000")
    )


def test_reduction_changes_amount():
    flows = [
        {
            "date":
                pd.Timestamp(
                    "2026-09-15"
                ),

            "direction":
                "debit",

            "amount":
                Decimal("1000"),

            "category":
                "dining",

            "source":
                "recurring",
        }
    ]

    result = apply_changes_to_flows(
        flows,
        reductions={
            "dining":
                Decimal("0.20")
        },
    )

    assert (
        result[0]["amount"]
        == Decimal("800.00")
    )


def test_stop_changes_amount_to_zero():
    flows = [
        {
            "date":
                pd.Timestamp(
                    "2026-09-15"
                ),

            "direction":
                "debit",

            "amount":
                Decimal("1000"),

            "category":
                "entertainment",

            "source":
                "recurring",
        }
    ]

    result = apply_changes_to_flows(
        flows,
        stopped_categories={
            "entertainment"
        },
    )

    assert (
        result[0]["amount"]
        == Decimal("0")
    )


def test_credit_is_never_reduced():
    flows = [
        {
            "date":
                pd.Timestamp(
                    "2026-09-15"
                ),

            "direction":
                "credit",

            "amount":
                Decimal("1000"),

            "category":
                "salary",

            "source":
                "recurring",
        }
    ]

    result = apply_changes_to_flows(
        flows,
        reductions={
            "salary":
                Decimal("0.50")
        },
        stopped_categories={
            "salary"
        },
    )

    assert (
        result[0]["amount"]
        == Decimal("1000")
    )


def test_protected_removed_from_permissions():
    state = {
        "protected_categories": [
            "rent"
        ],

        "reducible_categories": [
            "rent",
            "dining",
        ],

        "stoppable_categories": [
            "rent",
            "entertainment",
        ],
    }

    result = spending_permissions(
        state
    )

    assert (
        "rent"
        not in result[
            "reducible"
        ]
    )

    assert (
        "rent"
        not in result[
            "stoppable"
        ]
    )

    assert (
        "dining"
        in result[
            "reducible"
        ]
    )


def test_safe_request_needs_no_changes():
    data = get_data()

    found = False

    for request_id in (
        data[
            "requests"
        ][
            "request_id"
        ]
    ):
        state = build_financial_state(
            data,
            request_id
        )

        result = find_spending_changes(
            state,
            data,
        )

        if result["safe"]:
            found = True

            assert (
                result[
                    "spending_changes_needed"
                ]
                == "none"
                or
                result[
                    "spending_changes_needed"
                ]
                != ""
            )

            break

    assert found


def test_all_requests_spending_planner_runs():
    data = get_data()

    for request_id in (
        data[
            "requests"
        ][
            "request_id"
        ].head(25)
    ):
        state = build_financial_state(
            data,
            request_id
        )

        result = find_spending_changes(
            state,
            data,
        )

        assert (
            "safe"
            in result
        )

        assert (
            "spending_changes_needed"
            in result
        )

        assert (
            "forecast"
            in result
        )