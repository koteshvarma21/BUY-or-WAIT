from copy import deepcopy
from decimal import Decimal

import pandas as pd

from forecast import build_cashflows, simulate_forecast


ZERO = Decimal("0")

REDUCTION_STEPS = [
    Decimal("0.10"),
    Decimal("0.20"),
    Decimal("0.30"),
    Decimal("0.40"),
    Decimal("0.50"),
]


def dec(value):
    if value is None:
        return None

    if pd.isna(value):
        return None

    return Decimal(str(value))


def category_set(values):
    if values is None:
        return set()

    if isinstance(values, str):
        values = [values]

    result = set()

    for value in values:
        if value is None:
            continue

        text = str(value).strip().lower()

        if text:
            result.add(text)

    return result


def spending_permissions(state):
    protected = category_set(
        state.get(
            "protected_categories",
            []
        )
    )

    reducible = category_set(
        state.get(
            "reducible_categories",
            []
        )
    )

    stoppable = category_set(
        state.get(
            "stoppable_categories",
            []
        )
    )

    # Protected categories always win.
    reducible -= protected
    stoppable -= protected

    return {
        "protected": protected,
        "reducible": reducible,
        "stoppable": stoppable,
    }


def normalize_reductions(
    reductions
):
    if reductions is None:
        return {}

    result = {}

    for category, fraction in (
        reductions.items()
    ):
        name = str(
            category
        ).strip().lower()

        value = dec(
            fraction
        )

        if (
            not name
            or value is None
        ):
            continue

        if value < ZERO:
            value = ZERO

        if value > Decimal("1"):
            value = Decimal("1")

        result[name] = value

    return result


def apply_changes_to_flows(
    flows,
    reductions=None,
    stopped_categories=None,
    protected_categories=None,
):
    reductions = normalize_reductions(
        reductions
    )

    stopped = category_set(
        stopped_categories
    )

    protected = category_set(
        protected_categories
    )

    adjusted = []

    for flow in flows:
        item = deepcopy(
            flow
        )

        if (
            item.get("direction")
            != "debit"
        ):
            adjusted.append(
                item
            )
            continue

        category = str(
            item.get(
                "category",
                ""
            )
        ).strip().lower()

        if category in protected:
            adjusted.append(
                item
            )
            continue

        amount = dec(
            item.get(
                "amount"
            )
        )

        if amount is None:
            adjusted.append(
                item
            )
            continue

        original = amount

        if category in stopped:
            amount = ZERO

        elif category in reductions:
            amount = (
                amount
                * (
                    Decimal("1")
                    - reductions[
                        category
                    ]
                )
            )

        item[
            "original_amount"
        ] = original

        item[
            "amount"
        ] = amount

        item[
            "spending_adjusted"
        ] = (
            amount != original
        )

        adjusted.append(
            item
        )

    return adjusted


def simulate_adjusted_flows(
    state,
    flows,
    unresolved=None,
    extra_payments=None,
):
    flows = [
        deepcopy(flow)
        for flow in flows
    ]

    if unresolved is None:
        unresolved = []

    if extra_payments is None:
        extra_payments = []

    for payment in extra_payments:
        amount = dec(
            payment.get(
                "amount"
            )
        )

        if (
            amount is None
            or amount <= ZERO
        ):
            continue

        flows.append({
            "date":
                pd.Timestamp(
                    payment["date"]
                ).normalize(),

            "direction":
                "debit",

            "amount":
                amount,

            "category":
                "request_payment",

            "event_id":
                None,

            "source":
                payment.get(
                    "source",
                    "request"
                ),
        })

    flows.sort(
        key=lambda flow: (
            pd.Timestamp(
                flow["date"]
            ),
            (
                0
                if flow[
                    "direction"
                ] == "debit"
                else 1
            ),
        )
    )

    balance = state[
        "current_balance"
    ]

    minimum = state[
        "minimum_balance"
    ]

    if balance is None:
        raise ValueError(
            "Current balance is missing"
        )

    if minimum is None:
        raise ValueError(
            "Minimum balance is missing"
        )

    lowest = balance

    rows = [{
        "date":
            state[
                "request_date"
            ],

        "direction":
            "opening",

        "amount":
            ZERO,

        "category":
            "opening_balance",

        "source":
            "profile",

        "balance":
            balance,
    }]

    for flow in flows:
        date = pd.Timestamp(
            flow["date"]
        ).normalize()

        if (
            date
            < state[
                "request_date"
            ]
        ):
            continue

        if (
            date
            > state[
                "forecast_end"
            ]
        ):
            continue

        amount = dec(
            flow.get(
                "amount"
            )
        )

        if amount is None:
            continue

        direction = flow.get(
            "direction"
        )

        if direction == "debit":
            balance -= amount

        elif direction == "credit":
            balance += amount

        else:
            continue

        lowest = min(
            lowest,
            balance
        )

        rows.append({
            **flow,
            "date":
                date,
            "amount":
                amount,
            "balance":
                balance,
        })

    return {
        "timeline":
            pd.DataFrame(
                rows
            ),

        "ending_balance":
            balance,

        "minimum_projected_balance":
            lowest,

        "required_minimum_balance":
            minimum,

        "is_safe":
            lowest >= minimum,

        "unresolved_event_ids":
            unresolved,
    }


def simulate_with_spending_changes(
    state,
    data,
    reductions=None,
    stopped_categories=None,
    extra_payments=None,
):
    permissions = spending_permissions(
        state
    )

    reductions = normalize_reductions(
        reductions
    )

    stopped = category_set(
        stopped_categories
    )

    # Remove changes the user did not permit.
    reductions = {
        category: value
        for category, value
        in reductions.items()
        if category
        in permissions[
            "reducible"
        ]
    }

    stopped = (
        stopped
        & permissions[
            "stoppable"
        ]
    )

    flows, unresolved = (
        build_cashflows(
            state,
            data
        )
    )

    adjusted = apply_changes_to_flows(
        flows,
        reductions=
            reductions,
        stopped_categories=
            stopped,
        protected_categories=
            permissions[
                "protected"
            ],
    )

    return simulate_adjusted_flows(
        state,
        adjusted,
        unresolved=
            unresolved,
        extra_payments=
            extra_payments,
    )


def category_future_spending(
    state,
    data
):
    flows, _ = build_cashflows(
        state,
        data
    )

    totals = {}

    for flow in flows:
        if (
            flow.get(
                "direction"
            )
            != "debit"
        ):
            continue

        category = str(
            flow.get(
                "category",
                ""
            )
        ).strip().lower()

        if not category:
            continue

        amount = dec(
            flow.get(
                "amount"
            )
        )

        if amount is None:
            continue

        totals[
            category
        ] = (
            totals.get(
                category,
                ZERO
            )
            + amount
        )

    return totals


def describe_changes(
    reductions,
    stopped
):
    parts = []

    for category in sorted(
        reductions
    ):
        percent = int(
            reductions[
                category
            ]
            * 100
        )

        parts.append(
            f"reduce {category} "
            f"by {percent}%"
        )

    for category in sorted(
        stopped
    ):
        parts.append(
            f"stop {category}"
        )

    if not parts:
        return "none"

    return "; ".join(
        parts
    )


def build_result(
    safe,
    reductions,
    stopped,
    forecast,
):
    return {
        "safe":
            safe,

        "reductions":
            reductions,

        "stopped_categories":
            sorted(
                stopped
            ),

        "spending_changes_needed":
            describe_changes(
                reductions,
                stopped
            ),

        "forecast":
            forecast,
    }


def find_spending_changes(
    state,
    data,
    extra_payments=None,
):
    if extra_payments is None:
        extra_payments = []

    baseline = simulate_forecast(
        state,
        data,
        extra_payments=
            extra_payments,
    )

    if baseline["is_safe"]:
        return build_result(
            True,
            {},
            set(),
            baseline,
        )

    permissions = spending_permissions(
        state
    )

    reducible = permissions[
        "reducible"
    ]

    stoppable = permissions[
        "stoppable"
    ]

    if (
        not reducible
        and not stoppable
    ):
        return build_result(
            False,
            {},
            set(),
            baseline,
        )

    totals = category_future_spending(
        state,
        data
    )

    reducible = sorted(
        reducible,
        key=lambda category:
            totals.get(
                category,
                ZERO
            ),
        reverse=True,
    )

    stoppable = sorted(
        stoppable,
        key=lambda category:
            totals.get(
                category,
                ZERO
            ),
        reverse=True,
    )

    # First try reductions only.
    # Prefer changing fewer categories.
    for count in range(
        1,
        len(reducible) + 1
    ):
        selected = reducible[
            :count
        ]

        for fraction in (
            REDUCTION_STEPS
        ):
            reductions = {
                category:
                    fraction
                for category
                in selected
            }

            forecast = (
                simulate_with_spending_changes(
                    state,
                    data,
                    reductions=
                        reductions,
                    extra_payments=
                        extra_payments,
                )
            )

            if forecast[
                "is_safe"
            ]:
                return build_result(
                    True,
                    reductions,
                    set(),
                    forecast,
                )

    # Reduction alone was insufficient.
    # Use the maximum permitted reduction
    # before stopping categories.
    reductions = {
        category:
            REDUCTION_STEPS[-1]
        for category
        in reducible
    }

    stopped = set()

    for category in stoppable:
        stopped.add(
            category
        )

        forecast = (
            simulate_with_spending_changes(
                state,
                data,
                reductions=
                    reductions,
                stopped_categories=
                    stopped,
                extra_payments=
                    extra_payments,
            )
        )

        if forecast[
            "is_safe"
        ]:
            return build_result(
                True,
                reductions,
                stopped,
                forecast,
            )

    final_forecast = (
        simulate_with_spending_changes(
            state,
            data,
            reductions=
                reductions,
            stopped_categories=
                stopped,
            extra_payments=
                extra_payments,
        )
    )

    return build_result(
        final_forecast[
            "is_safe"
        ],
        reductions,
        stopped,
        final_forecast,
    )