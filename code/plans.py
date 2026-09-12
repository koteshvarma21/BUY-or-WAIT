from decimal import Decimal

import pandas as pd

from forecast import simulate_forecast
from safe_amount import calculate_safe_amount
from spending_changes import (
    describe_changes,
    find_spending_changes,
)


ZERO = Decimal("0")


def dec(value):
    if value is None or pd.isna(value):
        return None

    return Decimal(str(value))


def format_amount(value):
    value = dec(value)

    if value is None:
        return ""

    text = f"{value:.2f}"

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text


def format_payment_plan(payments):
    if not payments:
        return "none"

    payments = sorted(
        payments,
        key=lambda x: x["date"]
    )

    parts = []

    for payment in payments:
        date = pd.Timestamp(
            payment["date"]
        ).strftime("%Y-%m-%d")

        amount = format_amount(
            payment["amount"]
        )

        parts.append(
            f"{date}:{amount}"
        )

    return "|".join(parts)


def accepted_methods(state):
    methods = state.get(
        "payment_methods",
        []
    )

    if methods is None:
        return set()

    return {
        str(method).strip().lower()
        for method in methods
    }


def earliest_safe_full_payment_date(
    state,
    data,
    baseline=None
):
    if baseline is None:
        baseline = simulate_forecast(
            state,
            data
        )

    requested = state[
        "requested_amount"
    ]

    minimum = state[
        "minimum_balance"
    ]

    if requested is None:
        return None

    if not baseline["is_safe"]:
        return None

    timeline = baseline[
        "timeline"
    ].copy()

    timeline["date"] = pd.to_datetime(
        timeline["date"]
    ).dt.normalize()

    request_date = state[
        "request_date"
    ]

    forecast_end = state[
        "forecast_end"
    ]

    current_balance = state[
        "current_balance"
    ]

    for date in pd.date_range(
        request_date,
        forecast_end,
        freq="D",
    ):
        date = pd.Timestamp(
            date
        ).normalize()

        before = timeline[
            timeline["date"] < date
        ]

        if before.empty:
            balance_before = (
                current_balance
            )

        else:
            balance_before = (
                before.iloc[-1][
                    "balance"
                ]
            )

        future = timeline[
            timeline["date"] >= date
        ]

        balances = [
            balance_before
        ]

        balances.extend(
            future[
                "balance"
            ].tolist()
        )

        minimum_without_payment = min(
            balances
        )

        minimum_after_payment = (
            minimum_without_payment
            - requested
        )

        if (
            minimum_after_payment
            >= minimum
        ):
            return date

    return None


def build_candidate(
    method,
    status,
    payments,
    total_payable,
    financing_fee=ZERO,
    option_id=None,
    spending_changes_needed="none",
    spending_reductions=None,
    stopped_categories=None,
):
    payments = sorted(
        payments,
        key=lambda x: x["date"]
    )

    if spending_reductions is None:
        spending_reductions = {}

    if stopped_categories is None:
        stopped_categories = []

    return {
        "recommended_payment_method":
            method,

        "affordability_status":
            status,

        "payments":
            payments,

        "payment_plan":
            format_payment_plan(
                payments
            ),

        "start_date":
            (
                payments[0]["date"]
                if payments
                else None
            ),

        "last_payment_date":
            (
                payments[-1]["date"]
                if payments
                else None
            ),

        "number_of_payments":
            len(payments),

        "total_payable_amount":
            dec(total_payable),

        "financing_fee":
            dec(financing_fee)
            or ZERO,

        "payment_option_id":
            option_id,

        "spending_changes_needed":
            spending_changes_needed,

        "spending_reductions":
            spending_reductions,

        "stopped_categories":
            list(
                stopped_categories
            ),
    }


def apply_spending_result(
    candidate,
    spending_result
):
    reductions = dict(
        spending_result.get(
            "reductions",
            {}
        )
    )

    stopped = set(
        spending_result.get(
            "stopped_categories",
            []
        )
    )

    # If a category is stopped,
    # showing a reduction for it is redundant.
    reductions = {
        category: fraction
        for category, fraction
        in reductions.items()
        if category not in stopped
    }

    candidate[
        "spending_reductions"
    ] = reductions

    candidate[
        "stopped_categories"
    ] = sorted(
        stopped
    )

    candidate[
        "spending_changes_needed"
    ] = describe_changes(
        reductions,
        stopped
    )

    return candidate


def full_payment_candidate(
    state,
    data,
    safe_result
):
    methods = accepted_methods(
        state
    )

    if (
        "full_payment"
        not in methods
    ):
        return None

    if not safe_result[
        "can_pay_full_now"
    ]:
        return None

    requested = state[
        "requested_amount"
    ]

    payment = {
        "date":
            state[
                "request_date"
            ],

        "amount":
            requested,

        "source":
            "full_payment",
    }

    forecast = simulate_forecast(
        state,
        data,
        extra_payments=[
            payment
        ],
    )

    if not forecast["is_safe"]:
        return None

    return build_candidate(
        method="full_payment",
        status="affordable_now",
        payments=[payment],
        total_payable=requested,
    )


def partial_payment_candidate(
    state,
    data,
    safe_result,
    earliest_full_date,
):
    methods = accepted_methods(
        state
    )

    if (
        "partial_payment"
        not in methods
    ):
        return None

    if not state[
        "allows_partial_payment"
    ]:
        return None

    safe_now = safe_result[
        "amount_safe_to_pay"
    ]

    requested = state[
        "requested_amount"
    ]

    if (
        safe_now <= ZERO
        or safe_now >= requested
    ):
        return None

    if earliest_full_date is None:
        return None

    if (
        earliest_full_date
        > state[
            "desired_completion_date"
        ]
    ):
        return None

    remaining = (
        requested
        - safe_now
    )

    payments = [
        {
            "date":
                state[
                    "request_date"
                ],

            "amount":
                safe_now,

            "source":
                "partial_payment",
        },

        {
            "date":
                earliest_full_date,

            "amount":
                remaining,

            "source":
                "partial_payment",
        },
    ]

    forecast = simulate_forecast(
        state,
        data,
        extra_payments=payments,
    )

    if not forecast["is_safe"]:
        return None

    return build_candidate(
        method="partial_payment",
        status="affordable_with_plan",
        payments=payments,
        total_payable=requested,
    )


def installment_payments(option):
    amount = dec(
        option[
            "payment_amount"
        ]
    )

    if amount is None:
        return []

    number = int(
        option[
            "number_of_payments"
        ]
    )

    first_date = pd.Timestamp(
        option[
            "first_payment_date"
        ]
    ).normalize()

    frequency = int(
        option[
            "payment_frequency_days"
        ]
    )

    payments = []

    for index in range(number):
        date = (
            first_date
            + pd.Timedelta(
                days=(
                    index
                    * frequency
                )
            )
        )

        payments.append({
            "date":
                date,

            "amount":
                amount,

            "source":
                "installments",
        })

    return payments


def valid_installment_options(
    state
):
    methods = accepted_methods(
        state
    )

    if (
        "installments"
        not in methods
    ):
        return []

    max_months = state.get(
        "max_installment_months"
    )

    if max_months is None:
        return []

    options = state[
        "payment_options"
    ]

    options = options[
        options[
            "payment_method"
        ]
        == "installments"
    ]

    valid = []

    for _, option in (
        options.iterrows()
    ):
        if pd.isna(
            option[
                "number_of_payments"
            ]
        ):
            continue

        if pd.isna(
            option[
                "payment_frequency_days"
            ]
        ):
            continue

        if pd.isna(
            option[
                "first_payment_date"
            ]
        ):
            continue

        number = int(
            option[
                "number_of_payments"
            ]
        )

        if (
            number
            > int(max_months)
        ):
            continue

        payments = installment_payments(
            option
        )

        if not payments:
            continue

        first = payments[0][
            "date"
        ]

        last = payments[-1][
            "date"
        ]

        if (
            first
            < state[
                "request_date"
            ]
        ):
            continue

        if (
            last
            > state[
                "desired_completion_date"
            ]
        ):
            continue

        if (
            last
            > state[
                "forecast_end"
            ]
        ):
            continue

        valid.append(
            (
                option,
                payments,
            )
        )

    return valid


def installment_candidates(
    state,
    data
):
    result = []

    for (
        option,
        payments,
    ) in valid_installment_options(
        state
    ):
        forecast = simulate_forecast(
            state,
            data,
            extra_payments=payments,
        )

        if not forecast["is_safe"]:
            continue

        total_payable = dec(
            option[
                "total_payable_amount"
            ]
        )

        financing_fee = dec(
            option[
                "financing_fee"
            ]
        )

        candidate = build_candidate(
            method="installments",
            status="affordable_with_plan",
            payments=payments,
            total_payable=total_payable,
            financing_fee=(
                financing_fee
                or ZERO
            ),
            option_id=option[
                "payment_option_id"
            ],
        )

        result.append(
            candidate
        )

    return result


def wait_candidate(
    state,
    data,
    earliest_full_date,
):
    methods = accepted_methods(
        state
    )

    if (
        "full_payment"
        not in methods
    ):
        return None

    if earliest_full_date is None:
        return None

    if (
        earliest_full_date
        <= state[
            "request_date"
        ]
    ):
        return None

    if (
        earliest_full_date
        > state[
            "desired_completion_date"
        ]
    ):
        return None

    requested = state[
        "requested_amount"
    ]

    payment = {
        "date":
            earliest_full_date,

        "amount":
            requested,

        "source":
            "wait",
    }

    forecast = simulate_forecast(
        state,
        data,
        extra_payments=[
            payment
        ],
    )

    if not forecast["is_safe"]:
        return None

    return build_candidate(
        method="wait",
        status="affordable_later",
        payments=[payment],
        total_payable=requested,
    )


# -------------------------------------------------
# Spending-change rescue candidates
# -------------------------------------------------


def spending_full_candidate(
    state,
    data
):
    if (
        "full_payment"
        not in accepted_methods(
            state
        )
    ):
        return None

    requested = state[
        "requested_amount"
    ]

    payment = {
        "date":
            state[
                "request_date"
            ],

        "amount":
            requested,

        "source":
            "full_payment",
    }

    result = find_spending_changes(
        state,
        data,
        extra_payments=[
            payment
        ],
    )

    if not result["safe"]:
        return None

    if (
        result[
            "spending_changes_needed"
        ]
        == "none"
    ):
        status = (
            "affordable_now"
        )

    else:
        status = (
            "affordable_with_plan"
        )

    candidate = build_candidate(
        method="full_payment",
        status=status,
        payments=[payment],
        total_payable=requested,
    )

    return apply_spending_result(
        candidate,
        result,
    )


def spending_partial_candidate(
    state,
    data,
    safe_result,
):
    methods = accepted_methods(
        state
    )

    if (
        "partial_payment"
        not in methods
    ):
        return None

    if not state[
        "allows_partial_payment"
    ]:
        return None

    safe_now = safe_result[
        "amount_safe_to_pay"
    ]

    requested = state[
        "requested_amount"
    ]

    if (
        safe_now <= ZERO
        or safe_now >= requested
    ):
        return None

    end_date = state[
        "desired_completion_date"
    ]

    if (
        end_date
        <= state[
            "request_date"
        ]
    ):
        return None

    remaining = (
        requested
        - safe_now
    )

    payments = [
        {
            "date":
                state[
                    "request_date"
                ],

            "amount":
                safe_now,

            "source":
                "partial_payment",
        },

        {
            "date":
                end_date,

            "amount":
                remaining,

            "source":
                "partial_payment",
        },
    ]

    result = find_spending_changes(
        state,
        data,
        extra_payments=
            payments,
    )

    if not result["safe"]:
        return None

    candidate = build_candidate(
        method="partial_payment",
        status="affordable_with_plan",
        payments=payments,
        total_payable=requested,
    )

    return apply_spending_result(
        candidate,
        result,
    )


def spending_installment_candidates(
    state,
    data
):
    result = []

    for (
        option,
        payments,
    ) in valid_installment_options(
        state
    ):
        spending = (
            find_spending_changes(
                state,
                data,
                extra_payments=
                    payments,
            )
        )

        if not spending[
            "safe"
        ]:
            continue

        total_payable = dec(
            option[
                "total_payable_amount"
            ]
        )

        financing_fee = dec(
            option[
                "financing_fee"
            ]
        )

        candidate = build_candidate(
            method="installments",
            status="affordable_with_plan",
            payments=payments,
            total_payable=
                total_payable,
            financing_fee=(
                financing_fee
                or ZERO
            ),
            option_id=option[
                "payment_option_id"
            ],
        )

        candidate = (
            apply_spending_result(
                candidate,
                spending,
            )
        )

        result.append(
            candidate
        )

    return result


def spending_wait_candidate(
    state,
    data
):
    if (
        "full_payment"
        not in accepted_methods(
            state
        )
    ):
        return None

    payment_date = state[
        "desired_completion_date"
    ]

    if (
        payment_date
        <= state[
            "request_date"
        ]
    ):
        return None

    if (
        payment_date
        > state[
            "forecast_end"
        ]
    ):
        return None

    requested = state[
        "requested_amount"
    ]

    payment = {
        "date":
            payment_date,

        "amount":
            requested,

        "source":
            "wait",
    }

    spending = (
        find_spending_changes(
            state,
            data,
            extra_payments=[
                payment
            ],
        )
    )

    if not spending["safe"]:
        return None

    candidate = build_candidate(
        method="wait",
        status="affordable_later",
        payments=[
            payment
        ],
        total_payable=
            requested,
    )

    return apply_spending_result(
        candidate,
        spending,
    )


def generate_normal_candidates(
    state,
    data,
    safe_result,
    earliest_full_date,
):
    candidates = []

    full = full_payment_candidate(
        state,
        data,
        safe_result,
    )

    if full is not None:
        candidates.append(
            full
        )

    partial = (
        partial_payment_candidate(
            state,
            data,
            safe_result,
            earliest_full_date,
        )
    )

    if partial is not None:
        candidates.append(
            partial
        )

    candidates.extend(
        installment_candidates(
            state,
            data,
        )
    )

    wait = wait_candidate(
        state,
        data,
        earliest_full_date,
    )

    if wait is not None:
        candidates.append(
            wait
        )

    return candidates


def generate_spending_candidates(
    state,
    data,
    safe_result,
):
    candidates = []

    full = spending_full_candidate(
        state,
        data,
    )

    if full is not None:
        candidates.append(
            full
        )

    partial = (
        spending_partial_candidate(
            state,
            data,
            safe_result,
        )
    )

    if partial is not None:
        candidates.append(
            partial
        )

    candidates.extend(
        spending_installment_candidates(
            state,
            data,
        )
    )

    wait = spending_wait_candidate(
        state,
        data,
    )

    if wait is not None:
        candidates.append(
            wait
        )

    return candidates


def generate_plans(
    state,
    data
):
    safe_result = (
        calculate_safe_amount(
            state,
            data
        )
    )

    baseline = safe_result[
        "baseline_forecast"
    ]

    earliest_full_date = (
        earliest_safe_full_payment_date(
            state,
            data,
            baseline=baseline,
        )
    )

    candidates = (
        generate_normal_candidates(
            state,
            data,
            safe_result,
            earliest_full_date,
        )
    )

    # Ranking gives absolute preference
    # to avoiding spending changes.
    # Therefore, only run the more expensive
    # spending rescue search if no normal
    # candidate exists.
    if not candidates:
        candidates = (
            generate_spending_candidates(
                state,
                data,
                safe_result,
            )
        )

    if candidates:
        full_dates = []

        for candidate in candidates:
            method = candidate[
                "recommended_payment_method"
            ]

            if method in {
                "full_payment",
                "wait",
            }:
                date = candidate.get(
                    "start_date"
                )

                if date is not None:
                    full_dates.append(
                        pd.Timestamp(
                            date
                        ).normalize()
                    )

        if full_dates:
            rescue_date = min(
                full_dates
            )

            if (
                earliest_full_date
                is None
                or rescue_date
                < earliest_full_date
            ):
                earliest_full_date = (
                    rescue_date
                )

    return {
        "request_id":
            state[
                "request_id"
            ],

        "requested_amount":
            state[
                "requested_amount"
            ],

        "amount_safe_to_pay":
            safe_result[
                "amount_safe_to_pay"
            ],

        "earliest_date_for_full_payment":
            earliest_full_date,

        "baseline_is_safe":
            baseline[
                "is_safe"
            ],

        "candidates":
            candidates,
    }