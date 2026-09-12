import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"

sys.path.insert(0, str(CODE))

from loader import load_all
from normalizer import normalize_all
from financial_state import build_financial_state
from forecast import simulate_forecast
from spending_changes import simulate_with_spending_changes
from plans import (
    generate_plans,
    format_payment_plan,
)


def get_data():
    return normalize_all(
        load_all()
    )


def test_payment_plan_format():
    payments = [
        {
            "date": "2026-09-07",
            "amount": Decimal("300"),
        },
        {
            "date": "2026-10-07",
            "amount": Decimal("300"),
        },
    ]

    result = format_payment_plan(
        payments
    )

    assert result == (
        "2026-09-07:300"
        "|2026-10-07:300"
    )


def test_generate_plans_structure():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    result = generate_plans(
        state,
        data
    )

    assert (
        result["request_id"]
        == "request_33"
    )

    assert (
        "amount_safe_to_pay"
        in result
    )

    assert (
        "earliest_date_for_full_payment"
        in result
    )

    assert isinstance(
        result["candidates"],
        list
    )


def test_candidates_respect_deadline():
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

        result = generate_plans(
            state,
            data
        )

        for candidate in result[
            "candidates"
        ]:
            assert (
                candidate[
                    "last_payment_date"
                ]
                <=
                state[
                    "desired_completion_date"
                ]
            )


def test_every_generated_candidate_is_safe():
    data = get_data()

    request_ids = (
        data["requests"][
            "request_id"
        ]
        .head(25)
        .tolist()
    )

    for request_id in request_ids:
        state = build_financial_state(
            data,
            request_id
        )

        result = generate_plans(
            state,
            data
        )

        for candidate in result[
            "candidates"
        ]:

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
                forecast = (
                    simulate_with_spending_changes(
                        state,
                        data,
                        reductions=reductions,
                        stopped_categories=stopped,
                        extra_payments=
                            candidate[
                                "payments"
                            ],
                    )
                )

            else:
                forecast = (
                    simulate_forecast(
                        state,
                        data,
                        extra_payments=
                            candidate[
                                "payments"
                            ],
                    )
                )

            assert forecast[
                "is_safe"
            ], (
                request_id,
                candidate[
                    "recommended_payment_method"
                ],
                candidate.get(
                    "spending_changes_needed"
                ),
            )


def test_installments_match_supplied_option():
    data = get_data()

    request_ids = (
        data["requests"][
            "request_id"
        ]
        .head(50)
        .tolist()
    )

    for request_id in request_ids:
        state = build_financial_state(
            data,
            request_id
        )

        result = generate_plans(
            state,
            data
        )

        options = state[
            "payment_options"
        ]

        for candidate in result[
            "candidates"
        ]:

            if (
                candidate[
                    "recommended_payment_method"
                ]
                != "installments"
            ):
                continue

            option_id = candidate[
                "payment_option_id"
            ]

            row = options[
                options[
                    "payment_option_id"
                ]
                == option_id
            ].iloc[0]

            assert (
                candidate[
                    "number_of_payments"
                ]
                ==
                int(
                    row[
                        "number_of_payments"
                    ]
                )
            )

            assert (
                candidate[
                    "total_payable_amount"
                ]
                ==
                Decimal(
                    str(
                        row[
                            "total_payable_amount"
                        ]
                    )
                )
            )


def test_partial_plan_has_exactly_two_payments():
    data = get_data()

    request_ids = (
        data["requests"][
            "request_id"
        ]
        .head(100)
        .tolist()
    )

    for request_id in request_ids:
        state = build_financial_state(
            data,
            request_id
        )

        result = generate_plans(
            state,
            data
        )

        for candidate in result[
            "candidates"
        ]:

            if (
                candidate[
                    "recommended_payment_method"
                ]
                != "partial_payment"
            ):
                continue

            assert (
                candidate[
                    "number_of_payments"
                ]
                == 2
            )

            total = sum(
                payment["amount"]
                for payment
                in candidate[
                    "payments"
                ]
            )

            assert (
                total
                ==
                state[
                    "requested_amount"
                ]
            )


def test_all_requests_generate_plans():
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

        result = generate_plans(
            state,
            data
        )

        assert (
            result["request_id"]
            == request_id
        )

        assert (
            result[
                "amount_safe_to_pay"
            ]
            >= Decimal("0")
        )

        assert (
            result[
                "amount_safe_to_pay"
            ]
            <=
            state[
                "requested_amount"
            ]
        )