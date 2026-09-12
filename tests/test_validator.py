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
from validator import (
    validate_decision,
    require_valid_decision,
)


def get_data():
    return normalize_all(
        load_all()
    )


def test_real_decision_validates():
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

    result = validate_decision(
        state,
        data,
        decision
    )

    assert result["valid"]
    assert result["errors"] == []


def test_wrong_request_id_fails():
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

    decision["request_id"] = (
        "wrong_request"
    )

    result = validate_decision(
        state,
        data,
        decision
    )

    assert not result["valid"]


def test_invalid_method_fails():
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
    ] = "made_up_method"

    result = validate_decision(
        state,
        data,
        decision
    )

    assert not result["valid"]


def test_safe_amount_above_request_fails():
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
        "amount_safe_to_pay"
    ] = (
        state[
            "requested_amount"
        ]
        + 1
    )

    result = validate_decision(
        state,
        data,
        decision
    )

    assert not result["valid"]


def test_require_valid_returns_decision():
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

    checked = require_valid_decision(
        state,
        data,
        decision
    )

    assert checked is decision


def test_status_method_consistency():
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

    # Force a definitely invalid pair.
    # not_affordable is only valid with
    # not_recommended.
    decision[
        "affordability_status"
    ] = "not_affordable"

    decision[
        "recommended_payment_method"
    ] = "full_payment"

    result = validate_decision(
        state,
        data,
        decision
    )

    assert not result["valid"]

    assert any(
        "inconsistent" in error
        for error in result["errors"]
    )


def test_all_250_decisions_validate():
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

        result = validate_decision(
            state,
            data,
            decision
        )

        assert result["valid"], (
            request_id,
            result["errors"],
        )