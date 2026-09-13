import sys
from copy import deepcopy
from pathlib import Path


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
    generate_ranked_decision
)
from explanation import (
    attach_explanation,
    generate_explanation,
)


def get_data():
    return normalize_all(
        load_all()
    )


def test_real_decision_has_explanation():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    decision = (
        generate_ranked_decision(
            state,
            data
        )
    )

    text = generate_explanation(
        state,
        decision,
    )

    assert isinstance(
        text,
        str
    )

    assert len(
        text
    ) > 30


def test_attach_explanation():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    decision = (
        generate_ranked_decision(
            state,
            data
        )
    )

    result = attach_explanation(
        state,
        decision,
    )

    assert (
        "decision_explanation"
        in result
    )

    assert (
        result[
            "decision_explanation"
        ]
    )


def test_not_affordable_explanation():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    decision = {
        "request_id":
            state[
                "request_id"
            ],

        "amount_safe_to_pay":
            0,

        "affordability_status":
            "not_affordable",

        "recommended_payment_method":
            "not_recommended",

        "payment_plan":
            "none",

        "earliest_date_for_full_payment":
            None,

        "spending_changes_needed":
            "none",

        "selected_candidate":
            None,

        "candidate_count":
            0,
    }

    text = generate_explanation(
        state,
        decision,
    )

    assert (
        "cannot be completed safely"
        in text
    )


def test_explanation_mentions_spending_changes():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    decision = (
        generate_ranked_decision(
            state,
            data
        )
    )

    decision = deepcopy(
        decision
    )

    decision[
        "recommended_payment_method"
    ] = "full_payment"

    decision[
        "spending_changes_needed"
    ] = (
        "reduce dining by 20%"
    )

    text = generate_explanation(
        state,
        decision,
    )

    assert (
        "reduce dining by 20%"
        in text
    )


def test_all_250_decisions_get_explanation():
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

        decision = (
            generate_ranked_decision(
                state,
                data
            )
        )

        result = attach_explanation(
            state,
            decision,
        )

        text = result[
            "decision_explanation"
        ]

        assert isinstance(
            text,
            str
        )

        assert len(
            text
        ) > 20