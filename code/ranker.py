from decimal import Decimal

import pandas as pd

from plans import generate_plans


ZERO = Decimal("0")


METHOD_ORDER = {
    "full_payment": 0,
    "partial_payment": 1,
    "installments": 2,
    "wait": 3,
    "not_recommended": 4,
}


def dec(value):
    if value is None or pd.isna(value):
        return ZERO

    return Decimal(str(value))


def no_spending_changes(candidate):
    value = candidate.get(
        "spending_changes_needed"
    )

    if value is None:
        return True

    value = str(value).strip().lower()

    return value in {
        "",
        "none",
        "no",
        "not_needed",
        "not needed",
    }


def deadline_met(candidate, state):
    last_date = candidate.get(
        "last_payment_date"
    )

    if last_date is None:
        return False

    last_date = pd.Timestamp(
        last_date
    ).normalize()

    deadline = pd.Timestamp(
        state[
            "desired_completion_date"
        ]
    ).normalize()

    return last_date <= deadline


def candidate_rank_key(
    candidate,
    state
):
    """
    Lower tuple is better.

    Challenge priority:
    1. Meet the requested deadline.
    2. Avoid spending changes.
    3. Minimize total payable cost.
    4. Start payment earlier.
    5. Use fewer payments.
    6. Deterministic method/id tie-break.
    """

    deadline_score = (
        0
        if deadline_met(
            candidate,
            state
        )
        else 1
    )

    spending_score = (
        0
        if no_spending_changes(
            candidate
        )
        else 1
    )

    total_cost = dec(
        candidate.get(
            "total_payable_amount"
        )
    )

    start_date = candidate.get(
        "start_date"
    )

    if start_date is None:
        start_value = pd.Timestamp(
            "2262-04-11"
        )
    else:
        start_value = pd.Timestamp(
            start_date
        ).normalize()

    payment_count = int(
        candidate.get(
            "number_of_payments",
            10**9
        )
    )

    method = candidate.get(
        "recommended_payment_method",
        "not_recommended"
    )

    method_score = METHOD_ORDER.get(
        method,
        99
    )

    option_id = candidate.get(
        "payment_option_id"
    )

    if option_id is None or pd.isna(
        option_id
    ):
        option_id = ""

    option_id = str(option_id)

    return (
        deadline_score,
        spending_score,
        total_cost,
        start_value,
        payment_count,
        method_score,
        option_id,
    )


def choose_best_candidate(
    candidates,
    state
):
    if not candidates:
        return None

    return min(
        candidates,
        key=lambda candidate:
            candidate_rank_key(
                candidate,
                state
            )
    )


def not_affordable_decision(
    state,
    plan_result
):
    earliest = plan_result.get(
        "earliest_date_for_full_payment"
    )

    return {
        "request_id":
            state["request_id"],

        "amount_safe_to_pay":
            plan_result[
                "amount_safe_to_pay"
            ],

        "affordability_status":
            "not_affordable",

        "recommended_payment_method":
            "not_recommended",

        "payment_plan":
            "none",

        "earliest_date_for_full_payment":
            earliest,

        "spending_changes_needed":
            "none",

        "selected_candidate":
            None,

        "candidate_count":
            0,
    }


def build_decision_from_candidate(
    state,
    plan_result,
    candidate
):
    return {
        "request_id":
            state["request_id"],

        "amount_safe_to_pay":
            plan_result[
                "amount_safe_to_pay"
            ],

        "affordability_status":
            candidate[
                "affordability_status"
            ],

        "recommended_payment_method":
            candidate[
                "recommended_payment_method"
            ],

        "payment_plan":
            candidate[
                "payment_plan"
            ],

        "earliest_date_for_full_payment":
            plan_result[
                "earliest_date_for_full_payment"
            ],

        "spending_changes_needed":
            candidate.get(
                "spending_changes_needed",
                "none"
            ),

        "selected_candidate":
            candidate,

        "candidate_count":
            len(
                plan_result[
                    "candidates"
                ]
            ),
    }


def rank_plans(
    state,
    plan_result
):
    candidates = plan_result.get(
        "candidates",
        []
    )

    best = choose_best_candidate(
        candidates,
        state
    )

    if best is None:
        return not_affordable_decision(
            state,
            plan_result
        )

    return build_decision_from_candidate(
        state,
        plan_result,
        best
    )


def generate_ranked_decision(
    state,
    data
):
    plan_result = generate_plans(
        state,
        data
    )

    return rank_plans(
        state,
        plan_result
    )