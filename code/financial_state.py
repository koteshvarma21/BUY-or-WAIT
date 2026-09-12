from decimal import Decimal

import pandas as pd


FORECAST_DAYS = 90


def money(value):
    if pd.isna(value):
        return None

    return Decimal(str(value))


def get_one(df, column, value, label):
    rows = df[df[column] == value]

    if rows.empty:
        raise ValueError(
            f"{label} not found for {column}={value}"
        )

    if len(rows) > 1:
        raise ValueError(
            f"Multiple {label} rows found for {column}={value}"
        )

    return rows.iloc[0]


def get_request(data, request_id):
    return get_one(
        data["requests"],
        "request_id",
        request_id,
        "request"
    )


def get_profile(data, user_id):
    return get_one(
        data["financial_profiles"],
        "user_id",
        user_id,
        "financial profile"
    )


def get_user_events(data, user_id):
    events = data["financial_events"]

    result = events[
        events["user_id"] == user_id
    ].copy()

    return result.sort_values(
        by=["event_date", "settlement_date"],
        na_position="last"
    ).reset_index(drop=True)


def get_messages(
    data,
    user_id,
    request_id,
    request_date
):
    messages = data["messages"]

    rows = messages[
        messages["user_id"] == user_id
    ].copy()

    if rows.empty:
        return rows.reset_index(drop=True)

    # Only information available on or before request date.
    rows = rows[
        rows["sent_at"].dt.normalize()
        <= request_date.normalize()
    ]

    # Keep both:
    # 1. messages directly linked to this request
    # 2. user-wide messages with no request_id
    rows = rows[
        rows["request_id"].isna()
        | (rows["request_id"] == request_id)
    ]

    return rows.sort_values(
        "sent_at"
    ).reset_index(drop=True)


def get_images(
    data,
    user_id,
    request_id,
    event_ids
):
    images = data["images"]

    rows = images[
        images["user_id"] == user_id
    ].copy()

    if rows.empty:
        return rows.reset_index(drop=True)

    request_match = (
        rows["request_id"] == request_id
    )

    event_match = (
        rows["related_event_id"].isin(event_ids)
    )

    rows = rows[
        request_match | event_match
    ]

    return rows.reset_index(drop=True)


def get_payment_options(data, request_id):
    options = data["request_payment_options"]

    rows = options[
        options["request_id"] == request_id
    ].copy()

    return rows.sort_values(
        "payment_option_id"
    ).reset_index(drop=True)


def split_events(
    events,
    request_date,
    forecast_end
):
    events = events.copy()

    # Settlement date is the important cash-flow date.
    # Fall back to event_date when settlement_date is absent.
    events["effective_date"] = (
        events["settlement_date"]
        .fillna(events["event_date"])
    )

    past = events[
        events["event_date"] < request_date
    ].copy()

    window = events[
        (events["effective_date"] >= request_date)
        & (events["effective_date"] <= forecast_end)
    ].copy()

    return (
        past.reset_index(drop=True),
        window.reset_index(drop=True)
    )


def build_financial_state(data, request_id):
    request = get_request(
        data,
        request_id
    )

    user_id = request["user_id"]

    profile = get_profile(
        data,
        user_id
    )

    request_date = pd.Timestamp(
        request["request_date"]
    ).normalize()

    forecast_end = (
        request_date
        + pd.Timedelta(days=FORECAST_DAYS)
    )

    events = get_user_events(
        data,
        user_id
    )

    event_ids = set(
        events["event_id"]
        .dropna()
        .tolist()
    )

    messages = get_messages(
        data,
        user_id,
        request_id,
        request_date
    )

    images = get_images(
        data,
        user_id,
        request_id,
        event_ids
    )

    payment_options = get_payment_options(
        data,
        request_id
    )

    past_events, forecast_events = split_events(
        events,
        request_date,
        forecast_end
    )

    state = {
        "request_id": request_id,
        "user_id": user_id,

        "request_date": request_date,
        "forecast_end": forecast_end,

        "home_currency": profile["home_currency"],

        "current_balance": money(
            profile["current_available_balance"]
        ),

        "minimum_balance": money(
            profile["minimum_balance_to_keep"]
        ),

        "requested_amount": money(
            request["requested_amount"]
        ),

        "desired_completion_date": pd.Timestamp(
            request["desired_completion_date"]
        ).normalize(),

        "allows_partial_payment": bool(
            request["allows_partial_payment"]
        ),

        "payment_methods": profile.get(
            "payment_methods_user_will_consider_list",
            []
        ),

        "protected_categories": profile.get(
            "expense_categories_to_protect_list",
            []
        ),

        "reducible_categories": profile.get(
            "expense_categories_user_is_willing_to_reduce_list",
            []
        ),

        "stoppable_categories": profile.get(
            "expense_categories_user_is_willing_to_stop_list",
            []
        ),

        "max_installment_months": (
            None
            if pd.isna(profile["max_installment_months"])
            else int(profile["max_installment_months"])
        ),

        "request": request.copy(),
        "profile": profile.copy(),

        "all_events": events,
        "past_events": past_events,
        "forecast_events": forecast_events,

        "messages": messages,
        "images": images,
        "payment_options": payment_options,
    }

    return state