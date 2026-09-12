from decimal import Decimal

import pandas as pd

from forecast import simulate_forecast
from spending_changes import (
    simulate_with_spending_changes,
    spending_permissions,
)


ZERO = Decimal("0")
CENT = Decimal("0.01")


VALID_STATUSES = {
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
}


VALID_METHODS = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
}


STATUS_METHODS = {
    "affordable_now": {
        "full_payment",
    },

    "affordable_with_plan": {
        "full_payment",
        "partial_payment",
        "installments",
    },

    "affordable_later": {
        "wait",
    },

    "not_affordable": {
        "not_recommended",
    },
}


def dec(value):
    if value is None or pd.isna(value):
        return None

    return Decimal(str(value))


def close_money(a, b):
    a = dec(a)
    b = dec(b)

    if (
        a is None
        or b is None
    ):
        return False

    return (
        abs(a - b)
        <= CENT
    )


def validate_basic_fields(
    state,
    decision,
    errors,
):
    if (
        decision.get(
            "request_id"
        )
        != state[
            "request_id"
        ]
    ):
        errors.append(
            "request_id does not match state"
        )

    status = decision.get(
        "affordability_status"
    )

    method = decision.get(
        "recommended_payment_method"
    )

    if (
        status
        not in VALID_STATUSES
    ):
        errors.append(
            f"invalid affordability_status: "
            f"{status}"
        )

    if (
        method
        not in VALID_METHODS
    ):
        errors.append(
            f"invalid payment method: "
            f"{method}"
        )

    if (
        status in STATUS_METHODS
        and method
        not in STATUS_METHODS[
            status
        ]
    ):
        errors.append(
            "affordability status and "
            "payment method are inconsistent"
        )


def validate_safe_amount(
    state,
    decision,
    errors,
):
    amount = dec(
        decision.get(
            "amount_safe_to_pay"
        )
    )

    requested = state[
        "requested_amount"
    ]

    if amount is None:
        errors.append(
            "amount_safe_to_pay is missing"
        )
        return

    if amount < ZERO:
        errors.append(
            "amount_safe_to_pay is negative"
        )

    if amount > requested:
        errors.append(
            "amount_safe_to_pay exceeds "
            "requested amount"
        )


def validate_earliest_date(
    state,
    decision,
    errors,
):
    value = decision.get(
        "earliest_date_for_full_payment"
    )

    if (
        value is None
        or pd.isna(value)
    ):
        return

    date = pd.Timestamp(
        value
    ).normalize()

    if (
        date
        < state[
            "request_date"
        ]
    ):
        errors.append(
            "earliest full payment date "
            "is before request date"
        )

    if (
        date
        > state[
            "forecast_end"
        ]
    ):
        errors.append(
            "earliest full payment date "
            "is outside forecast window"
        )


def validate_no_plan_decision(
    decision,
    errors,
):
    if (
        decision[
            "affordability_status"
        ]
        != "not_affordable"
    ):
        return

    if (
        decision[
            "recommended_payment_method"
        ]
        != "not_recommended"
    ):
        errors.append(
            "not_affordable must use "
            "not_recommended"
        )

    if (
        decision.get(
            "selected_candidate"
        )
        is not None
    ):
        errors.append(
            "not_affordable decision "
            "must not have selected candidate"
        )


def payment_total(
    payments
):
    total = ZERO

    for payment in payments:
        amount = dec(
            payment.get(
                "amount"
            )
        )

        if amount is not None:
            total += amount

    return total


def validate_payment_dates(
    state,
    candidate,
    errors,
):
    payments = candidate.get(
        "payments",
        []
    )

    previous = None

    for payment in payments:
        date = payment.get(
            "date"
        )

        if date is None:
            errors.append(
                "payment date is missing"
            )
            continue

        date = pd.Timestamp(
            date
        ).normalize()

        if (
            date
            < state[
                "request_date"
            ]
        ):
            errors.append(
                "payment occurs before "
                "request date"
            )

        if (
            date
            > state[
                "desired_completion_date"
            ]
        ):
            errors.append(
                "payment occurs after "
                "desired completion date"
            )

        if (
            date
            > state[
                "forecast_end"
            ]
        ):
            errors.append(
                "payment occurs outside "
                "90-day forecast window"
            )

        if (
            previous is not None
            and date < previous
        ):
            errors.append(
                "payments are not in "
                "chronological order"
            )

        previous = date


def validate_payment_amounts(
    state,
    candidate,
    errors,
):
    payments = candidate.get(
        "payments",
        []
    )

    if not payments:
        errors.append(
            "selected candidate has no payments"
        )
        return

    for payment in payments:
        amount = dec(
            payment.get(
                "amount"
            )
        )

        if amount is None:
            errors.append(
                "payment amount is missing"
            )

        elif amount <= ZERO:
            errors.append(
                "payment amount must be positive"
            )

    total = payment_total(
        payments
    )

    method = candidate[
        "recommended_payment_method"
    ]

    if method in {
        "full_payment",
        "partial_payment",
        "wait",
    }:
        if not close_money(
            total,
            state[
                "requested_amount"
            ],
        ):
            errors.append(
                "payment total does not equal "
                "requested amount"
            )

    total_payable = dec(
        candidate.get(
            "total_payable_amount"
        )
    )

    if total_payable is None:
        errors.append(
            "total payable amount is missing"
        )

    elif not close_money(
        total,
        total_payable,
    ):
        errors.append(
            "payment schedule total does not "
            "match total payable amount"
        )


def validate_installment_option(
    state,
    candidate,
    errors,
):
    if (
        candidate[
            "recommended_payment_method"
        ]
        != "installments"
    ):
        return

    option_id = candidate.get(
        "payment_option_id"
    )

    if (
        option_id is None
        or pd.isna(
            option_id
        )
    ):
        errors.append(
            "installment candidate has "
            "no payment_option_id"
        )
        return

    options = state[
        "payment_options"
    ]

    match = options[
        options[
            "payment_option_id"
        ]
        == option_id
    ]

    if match.empty:
        errors.append(
            "installment option was not "
            "provided by dataset"
        )
        return

    if len(match) != 1:
        errors.append(
            "duplicate installment option id"
        )
        return

    option = match.iloc[0]

    if (
        option[
            "payment_method"
        ]
        != "installments"
    ):
        errors.append(
            "selected option is not an "
            "installment option"
        )

    expected_count = int(
        option[
            "number_of_payments"
        ]
    )

    actual_count = len(
        candidate.get(
            "payments",
            []
        )
    )

    if (
        actual_count
        != expected_count
    ):
        errors.append(
            "installment payment count "
            "does not match dataset"
        )

    expected_total = dec(
        option[
            "total_payable_amount"
        ]
    )

    candidate_total = dec(
        candidate[
            "total_payable_amount"
        ]
    )

    if not close_money(
        expected_total,
        candidate_total,
    ):
        errors.append(
            "installment total payable "
            "does not match dataset"
        )

    expected_fee = dec(
        option[
            "financing_fee"
        ]
    )

    candidate_fee = dec(
        candidate[
            "financing_fee"
        ]
    )

    expected_fee = (
        expected_fee
        if expected_fee is not None
        else ZERO
    )

    candidate_fee = (
        candidate_fee
        if candidate_fee is not None
        else ZERO
    )

    if not close_money(
        expected_fee,
        candidate_fee,
    ):
        errors.append(
            "installment financing fee "
            "does not match dataset"
        )


def validate_spending_changes(
    state,
    candidate,
    errors,
):
    permissions = (
        spending_permissions(
            state
        )
    )

    protected = permissions[
        "protected"
    ]

    reducible = permissions[
        "reducible"
    ]

    stoppable = permissions[
        "stoppable"
    ]

    reductions = candidate.get(
        "spending_reductions",
        {},
    )

    stopped = set(
        candidate.get(
            "stopped_categories",
            [],
        )
    )

    for category, fraction in (
        reductions.items()
    ):
        category = str(
            category
        ).strip().lower()

        fraction = dec(
            fraction
        )

        if category in protected:
            errors.append(
                f"protected category changed: "
                f"{category}"
            )

        if (
            category
            not in reducible
        ):
            errors.append(
                f"category not allowed "
                f"to reduce: {category}"
            )

        if (
            fraction is None
            or fraction <= ZERO
            or fraction > Decimal("1")
        ):
            errors.append(
                f"invalid reduction for "
                f"{category}"
            )

    for category in stopped:
        category = str(
            category
        ).strip().lower()

        if category in protected:
            errors.append(
                f"protected category stopped: "
                f"{category}"
            )

        if (
            category
            not in stoppable
        ):
            errors.append(
                f"category not allowed "
                f"to stop: {category}"
            )

    description = str(
        candidate.get(
            "spending_changes_needed",
            "none",
        )
    ).strip().lower()

    has_changes = bool(
        reductions
        or stopped
    )

    if (
        has_changes
        and description == "none"
    ):
        errors.append(
            "spending changes exist but "
            "description says none"
        )

    if (
        not has_changes
        and description != "none"
    ):
        errors.append(
            "spending change description "
            "exists without actual changes"
        )

    if (
        candidate[
            "affordability_status"
        ]
        == "affordable_now"
        and has_changes
    ):
        errors.append(
            "affordable_now cannot require "
            "spending changes"
        )


def validate_forecast_safety(
    state,
    data,
    candidate,
    errors,
):
    payments = candidate.get(
        "payments",
        []
    )

    reductions = candidate.get(
        "spending_reductions",
        {},
    )

    stopped = candidate.get(
        "stopped_categories",
        [],
    )

    has_changes = bool(
        reductions
        or stopped
    )

    if has_changes:
        result = (
            simulate_with_spending_changes(
                state,
                data,
                reductions=
                    reductions,
                stopped_categories=
                    stopped,
                extra_payments=
                    payments,
            )
        )

    else:
        result = simulate_forecast(
            state,
            data,
            extra_payments=
                payments,
        )

    if not result["is_safe"]:
        errors.append(
            "selected payment plan violates "
            "minimum balance"
        )


def validate_candidate(
    state,
    data,
    decision,
    errors,
):
    candidate = decision.get(
        "selected_candidate"
    )

    if candidate is None:
        if (
            decision[
                "affordability_status"
            ]
            != "not_affordable"
        ):
            errors.append(
                "affordable decision has "
                "no selected candidate"
            )

        return

    if (
        candidate[
            "recommended_payment_method"
        ]
        != decision[
            "recommended_payment_method"
        ]
    ):
        errors.append(
            "selected candidate method "
            "does not match decision"
        )

    if (
        candidate[
            "affordability_status"
        ]
        != decision[
            "affordability_status"
        ]
    ):
        errors.append(
            "selected candidate status "
            "does not match decision"
        )

    validate_payment_dates(
        state,
        candidate,
        errors,
    )

    validate_payment_amounts(
        state,
        candidate,
        errors,
    )

    validate_installment_option(
        state,
        candidate,
        errors,
    )

    validate_spending_changes(
        state,
        candidate,
        errors,
    )

    validate_forecast_safety(
        state,
        data,
        candidate,
        errors,
    )


def validate_decision(
    state,
    data,
    decision,
):
    errors = []

    validate_basic_fields(
        state,
        decision,
        errors,
    )

    validate_safe_amount(
        state,
        decision,
        errors,
    )

    validate_earliest_date(
        state,
        decision,
        errors,
    )

    validate_no_plan_decision(
        decision,
        errors,
    )

    validate_candidate(
        state,
        data,
        decision,
        errors,
    )

    return {
        "valid":
            len(errors) == 0,

        "errors":
            errors,

        "request_id":
            state[
                "request_id"
            ],
    }


def require_valid_decision(
    state,
    data,
    decision,
):
    result = validate_decision(
        state,
        data,
        decision,
    )

    if not result["valid"]:
        message = "; ".join(
            result[
                "errors"
            ]
        )

        raise ValueError(
            "Invalid decision for "
            f"{state['request_id']}: "
            f"{message}"
        )

    return decision