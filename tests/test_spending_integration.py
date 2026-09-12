import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parent.parent

CODE = ROOT / "code"

sys.path.insert(
    0,
    str(CODE)
)


from plans import (
    apply_spending_result,
)
from validator import (
    validate_spending_changes,
)


def test_stopped_category_removes_redundant_reduction():
    candidate = {
        "spending_reductions": {},
        "stopped_categories": [],
        "spending_changes_needed": "none",
    }

    spending = {
        "reductions": {
            "dining":
                Decimal("0.20"),

            "entertainment":
                Decimal("0.50"),
        },

        "stopped_categories": [
            "entertainment"
        ],
    }

    result = apply_spending_result(
        candidate,
        spending,
    )

    assert (
        "entertainment"
        not in result[
            "spending_reductions"
        ]
    )

    assert (
        result[
            "spending_reductions"
        ][
            "dining"
        ]
        == Decimal("0.20")
    )

    assert (
        result[
            "stopped_categories"
        ]
        == [
            "entertainment"
        ]
    )


def test_validator_accepts_allowed_reduction():
    state = {
        "protected_categories": [
            "rent"
        ],

        "reducible_categories": [
            "dining"
        ],

        "stoppable_categories": [
            "entertainment"
        ],
    }

    candidate = {
        "affordability_status":
            "affordable_with_plan",

        "spending_reductions": {
            "dining":
                Decimal("0.20")
        },

        "stopped_categories":
            [],

        "spending_changes_needed":
            "reduce dining by 20%",
    }

    errors = []

    validate_spending_changes(
        state,
        candidate,
        errors,
    )

    assert errors == []


def test_validator_rejects_protected_reduction():
    state = {
        "protected_categories": [
            "rent"
        ],

        "reducible_categories": [
            "dining"
        ],

        "stoppable_categories": [
            "entertainment"
        ],
    }

    candidate = {
        "affordability_status":
            "affordable_with_plan",

        "spending_reductions": {
            "rent":
                Decimal("0.20")
        },

        "stopped_categories":
            [],

        "spending_changes_needed":
            "reduce rent by 20%",
    }

    errors = []

    validate_spending_changes(
        state,
        candidate,
        errors,
    )

    assert errors


def test_validator_rejects_unapproved_stop():
    state = {
        "protected_categories":
            [],

        "reducible_categories":
            [],

        "stoppable_categories": [
            "entertainment"
        ],
    }

    candidate = {
        "affordability_status":
            "affordable_with_plan",

        "spending_reductions":
            {},

        "stopped_categories": [
            "groceries"
        ],

        "spending_changes_needed":
            "stop groceries",
    }

    errors = []

    validate_spending_changes(
        state,
        candidate,
        errors,
    )

    assert errors