from decimal import Decimal

import pandas as pd

from forecast import simulate_forecast
from safe_amount import calculate_safe_amount


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
        str(x).strip().lower()
        for x in methods
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

    # If the user's finances already violate
    # the minimum without this request,
    # a no-change payment plan cannot be safe.
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
        freq="D"
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
            balance_before = before.iloc[
                -1
            ]["balance"]

        future = timeline[
            timeline["date"] >= date
        ]

        balances = [
            balance_before
        ]

        balances.extend(
            future["balance"].tolist()
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
    option_id=None
):
    payments = sorted(
        payments,
        key=lambda x: x["date"]
    )

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
            "none"
    }


def full_payment_candidate(
    state,
    data,
    safe_result
):
    methods = accepted_methods(
        state
    )

    if "full_payment" not in methods:
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
            state["request_date"],

        "amount":
            requested,

        "source":
            "full_payment"
    }

    forecast = simulate_forecast(
        state,
        data,
        extra_payments=[payment]
    )

    if not forecast["is_safe"]:
        return None

    return build_candidate(
        method="full_payment",
        status="affordable_now",
        payments=[payment],
        total_payable=requested,
        financing_fee=ZERO
    )


def partial_payment_candidate(
    state,
    data,
    safe_result,
    earliest_full_date
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

    desired = state[
        "desired_completion_date"
    ]

    if (
        earliest_full_date
        > desired
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
                "partial_payment"
        },

        {
            "date":
                earliest_full_date,

            "amount":
                remaining,

            "source":
                "partial_payment"
        }
    ]

    forecast = simulate_forecast(
        state,
        data,
        extra_payments=payments
    )

    if not forecast["is_safe"]:
        return None

    return build_candidate(
        method="partial_payment",
        status="affordable_with_plan",
        payments=payments,
        total_payable=requested,
        financing_fee=ZERO
    )


def installment_payments(option):
    amount = dec(
        option["payment_amount"]
    )

    number = int(
        option["number_of_payments"]
    )

    first_date = pd.Timestamp(
        option["first_payment_date"]
    ).normalize()

    frequency = int(
        option["payment_frequency_days"]
    )

    payments = []

    for i in range(number):
        date = (
            first_date
            + pd.Timedelta(
                days=i * frequency
            )
        )

        payments.append({
            "date":
                date,

            "amount":
                amount,

            "source":
                "installments"
        })

    return payments


def installment_candidates(
    state,
    data
):
    methods = accepted_methods(
        state
    )

    if "installments" not in methods:
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
        options["payment_method"]
        == "installments"
    ]

    result = []

    for _, option in options.iterrows():

        if pd.isna(
            option["number_of_payments"]
        ):
            continue

        if pd.isna(
            option[
                "payment_frequency_days"
            ]
        ):
            continue

        number = int(
            option[
                "number_of_payments"
            ]
        )

        # Dataset installment schedules
        # are monthly (28/30/31 days).
        if number > int(max_months):
            continue

        payments = installment_payments(
            option
        )

        if not payments:
            continue

        first = payments[0]["date"]
        last = payments[-1]["date"]

        if (
            first
            < state["request_date"]
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
            > state["forecast_end"]
        ):
            continue

        forecast = simulate_forecast(
            state,
            data,
            extra_payments=payments
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
            ]
        )

        result.append(
            candidate
        )

    return result


def wait_candidate(
    state,
    data,
    earliest_full_date
):
    methods = accepted_methods(
        state
    )

    if "full_payment" not in methods:
        return None

    if earliest_full_date is None:
        return None

    if (
        earliest_full_date
        <= state["request_date"]
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
            "wait"
    }

    forecast = simulate_forecast(
        state,
        data,
        extra_payments=[payment]
    )

    if not forecast["is_safe"]:
        return None

    return build_candidate(
        method="wait",
        status="affordable_later",
        payments=[payment],
        total_payable=requested,
        financing_fee=ZERO
    )


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
            baseline=baseline
        )
    )

    candidates = []

    full = full_payment_candidate(
        state,
        data,
        safe_result
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
            earliest_full_date
        )
    )

    if partial is not None:
        candidates.append(
            partial
        )

    installments = (
        installment_candidates(
            state,
            data
        )
    )

    candidates.extend(
        installments
    )

    wait = wait_candidate(
        state,
        data,
        earliest_full_date
    )

    if wait is not None:
        candidates.append(
            wait
        )

    return {
        "request_id":
            state["request_id"],

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
            baseline["is_safe"],

        "candidates":
            candidates
    }