from decimal import Decimal

import pandas as pd


ZERO = Decimal("0")


def dec(value):
    if value is None or pd.isna(value):
        return None

    return Decimal(str(value))


def format_money(value):
    value = dec(value)

    if value is None:
        return "unknown"

    text = f"{value:.2f}"

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text


def format_date(value):
    if value is None or pd.isna(value):
        return None

    return pd.Timestamp(
        value
    ).strftime("%Y-%m-%d")


def explain_full_payment(
    state,
    decision,
):
    amount = format_money(
        state[
            "requested_amount"
        ]
    )

    safe = format_money(
        decision[
            "amount_safe_to_pay"
        ]
    )

    changes = decision.get(
        "spending_changes_needed",
        "none"
    )

    if (
        changes
        and changes != "none"
    ):
        return (
            f"The full payment of {amount} is "
            f"safe within the 90-day forecast "
            f"only with these allowed spending "
            f"changes: {changes}. "
            f"The amount considered safe to pay "
            f"immediately without exceeding the "
            f"request is {safe}."
        )

    return (
        f"The full payment of {amount} can be "
        f"made now while keeping the projected "
        f"90-day balance at or above the required "
        f"minimum balance. The safe amount to pay "
        f"now is {safe}."
    )


def explain_partial_payment(
    state,
    decision,
):
    candidate = decision.get(
        "selected_candidate"
    )

    payments = (
        candidate.get(
            "payments",
            []
        )
        if candidate
        else []
    )

    first_amount = None
    second_amount = None
    second_date = None

    if len(payments) >= 1:
        first_amount = format_money(
            payments[0][
                "amount"
            ]
        )

    if len(payments) >= 2:
        second_amount = format_money(
            payments[1][
                "amount"
            ]
        )

        second_date = format_date(
            payments[1][
                "date"
            ]
        )

    text = (
        f"Paying the full requested amount now "
        f"is not the selected safe option. "
        f"A partial payment of "
        f"{first_amount or 'the safe amount'} "
        f"can be made now"
    )

    if second_amount is not None:
        text += (
            f", with the remaining "
            f"{second_amount}"
        )

        if second_date is not None:
            text += (
                f" paid on {second_date}"
            )

    text += (
        ". This plan keeps the projected "
        "90-day balance above the required "
        "minimum."
    )

    changes = decision.get(
        "spending_changes_needed",
        "none"
    )

    if (
        changes
        and changes != "none"
    ):
        text += (
            f" It also requires these allowed "
            f"spending changes: {changes}."
        )

    return text


def explain_installments(
    state,
    decision,
):
    candidate = decision.get(
        "selected_candidate"
    )

    count = (
        candidate.get(
            "number_of_payments"
        )
        if candidate
        else None
    )

    total = (
        format_money(
            candidate.get(
                "total_payable_amount"
            )
        )
        if candidate
        else "unknown"
    )

    fee = (
        format_money(
            candidate.get(
                "financing_fee"
            )
        )
        if candidate
        else "0"
    )

    text = (
        f"A provided installment option is the "
        f"selected safe plan"
    )

    if count is not None:
        text += (
            f" with {count} payments"
        )

    text += (
        f". The total payable amount is {total}"
    )

    if fee != "0":
        text += (
            f", including a financing fee of "
            f"{fee}"
        )

    text += (
        ". The installment schedule stays "
        "within the requested completion date "
        "and keeps the projected 90-day balance "
        "at or above the required minimum."
    )

    changes = decision.get(
        "spending_changes_needed",
        "none"
    )

    if (
        changes
        and changes != "none"
    ):
        text += (
            f" The plan requires these allowed "
            f"spending changes: {changes}."
        )

    return text


def explain_wait(
    state,
    decision,
):
    date = format_date(
        decision.get(
            "earliest_date_for_full_payment"
        )
    )

    amount = format_money(
        state[
            "requested_amount"
        ]
    )

    if date is None:
        date_text = (
            "a later safe date"
        )
    else:
        date_text = date

    text = (
        f"The full amount of {amount} is not "
        f"the selected safe payment today. "
        f"Waiting until {date_text} allows the "
        f"full payment while keeping the "
        f"projected 90-day balance above the "
        f"required minimum."
    )

    changes = decision.get(
        "spending_changes_needed",
        "none"
    )

    if (
        changes
        and changes != "none"
    ):
        text += (
            f" This also requires these allowed "
            f"spending changes: {changes}."
        )

    return text


def explain_not_affordable(
    state,
    decision,
):
    requested = format_money(
        state[
            "requested_amount"
        ]
    )

    safe = format_money(
        decision[
            "amount_safe_to_pay"
        ]
    )

    return (
        f"The requested amount of {requested} "
        f"cannot be completed safely within the "
        f"available payment options and deadline "
        f"while maintaining the required minimum "
        f"balance over the 90-day forecast. "
        f"The amount currently safe to pay is "
        f"{safe}."
    )


def generate_explanation(
    state,
    decision,
):
    method = decision.get(
        "recommended_payment_method"
    )

    if method == "full_payment":
        return explain_full_payment(
            state,
            decision,
        )

    if method == "partial_payment":
        return explain_partial_payment(
            state,
            decision,
        )

    if method == "installments":
        return explain_installments(
            state,
            decision,
        )

    if method == "wait":
        return explain_wait(
            state,
            decision,
        )

    return explain_not_affordable(
        state,
        decision,
    )


def attach_explanation(
    state,
    decision,
):
    result = dict(
        decision
    )

    result[
        "decision_explanation"
    ] = generate_explanation(
        state,
        decision,
    )

    return result