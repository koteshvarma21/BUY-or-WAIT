import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"

sys.path.insert(0, str(CODE))

from loader import load_all
from normalizer import normalize_all
from financial_state import build_financial_state


def get_data():
    return normalize_all(load_all())


def test_build_state():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    assert state["request_id"] == "request_33"
    assert state["user_id"] == "user_33"
    assert state["current_balance"] is not None
    assert state["minimum_balance"] is not None

    assert (
        state["forecast_end"]
        - state["request_date"]
    ).days == 90


def test_request_has_image():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    assert "image_06" in (
        state["images"]["image_id"].tolist()
    )


def test_payment_options_exist():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    assert len(state["payment_options"]) == 2


def test_messages_not_after_request():
    data = get_data()

    state = build_financial_state(
        data,
        "request_33"
    )

    if not state["messages"].empty:
        dates = state["messages"]["sent_at"].dt.normalize()

        assert (
            dates <= state["request_date"]
        ).all()


def test_unknown_request():
    data = get_data()

    try:
        build_financial_state(
            data,
            "request_DOES_NOT_EXIST"
        )
        assert False

    except ValueError:
        assert True


def test_all_requests_can_build_state():
    data = get_data()

    for request_id in data["requests"]["request_id"]:
        state = build_financial_state(
            data,
            request_id
        )

        assert state["request_id"] == request_id
        assert state["user_id"] is not None