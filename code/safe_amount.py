from decimal import Decimal

from forecast import simulate_forecast


ZERO = Decimal("0")


def calculate_headroom(forecast_result):
    lowest_balance = forecast_result[
        "minimum_projected_balance"
    ]

    minimum_balance = forecast_result[
        "required_minimum_balance"
    ]

    headroom = (
        lowest_balance
        - minimum_balance
    )

    if headroom < ZERO:
        return ZERO

    return headroom


def calculate_safe_amount(
    state,
    data
):
    requested_amount = state[
        "requested_amount"
    ]

    if requested_amount is None:
        raise ValueError(
            "Requested amount is missing"
        )

    if requested_amount < ZERO:
        raise ValueError(
            "Requested amount cannot be negative"
        )

    baseline = simulate_forecast(
        state,
        data
    )

    headroom = calculate_headroom(
        baseline
    )

    safe_amount = min(
        requested_amount,
        headroom
    )

    if safe_amount < ZERO:
        safe_amount = ZERO

    can_pay_full_now = (
        safe_amount
        >= requested_amount
        and baseline["is_safe"]
    )

    payment_forecast = None

    if safe_amount > ZERO:
        payment_forecast = (
            simulate_forecast(
                state,
                data,
                extra_payments=[
                    {
                        "date":
                            state[
                                "request_date"
                            ],
                        "amount":
                            safe_amount,
                        "source":
                            "safe_amount"
                    }
                ]
            )
        )

    return {
        "requested_amount":
            requested_amount,

        "amount_safe_to_pay":
            safe_amount,

        "forecast_headroom":
            headroom,

        "can_pay_full_now":
            can_pay_full_now,

        "baseline_is_safe":
            baseline["is_safe"],

        "baseline_minimum_balance":
            baseline[
                "minimum_projected_balance"
            ],

        "required_minimum_balance":
            baseline[
                "required_minimum_balance"
            ],

        "baseline_forecast":
            baseline,

        "payment_forecast":
            payment_forecast,

        "unresolved_event_ids":
            baseline[
                "unresolved_event_ids"
            ]
    }


def amount_safe_to_pay(
    state,
    data
):
    result = calculate_safe_amount(
        state,
        data
    )

    return result[
        "amount_safe_to_pay"
    ]