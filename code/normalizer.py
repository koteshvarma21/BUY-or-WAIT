import pandas as pd


PROFILE_LIST_COLUMNS = [
    "financial_priorities",
    "expense_categories_to_protect",
    "expense_categories_user_is_willing_to_reduce",
    "expense_categories_user_is_willing_to_stop",
    "payment_methods_user_will_consider",
]

DATE_COLUMNS = {
    "financial_events": ["event_date", "settlement_date"],
    "exchange_rates": ["rate_date"],
    "requests": ["request_date", "desired_completion_date"],
    "sample_requests": [
        "request_date",
        "desired_completion_date",
        "earliest_date_for_full_payment",
    ],
    "request_payment_options": ["first_payment_date"],
    "messages": ["sent_at"],
}

ID_COLUMNS = {
    "financial_profiles": ["user_id"],
    "financial_events": ["event_id", "user_id", "linked_event_id"],
    "requests": ["request_id", "user_id"],
    "sample_requests": ["request_id", "user_id"],
    "request_payment_options": ["payment_option_id", "request_id"],
    "messages": [
        "message_id",
        "user_id",
        "request_id",
        "related_event_id",
    ],
    "images": [
        "image_id",
        "user_id",
        "request_id",
        "related_event_id",
    ],
    "output": ["request_id"],
}

LOWER_COLUMNS = {
    "financial_profiles": ["home_currency"],
    "financial_events": [
        "event_type",
        "category",
        "direction",
        "currency",
        "status",
        "flexibility",
    ],
    "exchange_rates": ["from_currency", "to_currency"],
    "requests": ["request_type"],
    "sample_requests": [
        "request_type",
        "affordability_status",
        "recommended_payment_method",
    ],
    "request_payment_options": ["payment_method"],
    "messages": ["source_type"],
}


def split_pipe(value):
    if pd.isna(value) or str(value).strip() == "":
        return []

    return [
        item.strip().lower()
        for item in str(value).split("|")
        if item.strip()
    ]


def normalize_ids(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
            # Keep empty ID fields nullish instead of converting to the
            # literal string 'nan' or introducing a float-like nonsense.
            df[col] = df[col].replace("", pd.NA)

    return df


def normalize_dates(df, columns):
    for col in columns:
        if col not in df.columns:
            continue

        if col == "sent_at":
            # Convert message timestamps to a safe challenge-naive form.
            # The incoming timestamps are UTC-aware strings in messages.csv,
            # so first parse as UTC and then drop timezone information.
            df[col] = pd.to_datetime(
                df[col],
                errors="coerce",
                utc=True,
            ).dt.tz_convert(None)
        else:
            df[col] = pd.to_datetime(
                df[col],
                errors="coerce",
            )

    return df


def normalize_text(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

            # Keep currencies uppercase
            if "currency" in col:
                df[col] = df[col].str.upper()
            else:
                df[col] = df[col].str.lower()

    return df


def normalize_profiles(df):
    df = df.copy()

    for col in PROFILE_LIST_COLUMNS:
        if col in df.columns:
            df[col + "_list"] = df[col].apply(split_pipe)

    if "max_installment_months" in df.columns:
        df["max_installment_months"] = pd.to_numeric(
            df["max_installment_months"],
            errors="coerce",
        ).astype("Int64")

    return df


def normalize_requests(df):
    df = df.copy()

    if "allows_partial_payment" in df.columns:
        df["allows_partial_payment"] = (
            df["allows_partial_payment"]
            .astype("boolean")
        )

    return df


def normalize_numeric(df):
    df = df.copy()

    numeric_columns = [
        "current_available_balance",
        "minimum_balance_to_keep",
        "amount",
        "minimum_allowed_amount",
        "rate",
        "requested_amount",
        "amount_safe_to_pay",
        "payment_amount",
        "number_of_payments",
        "payment_frequency_days",
        "financing_fee",
        "total_payable_amount",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    return df


def normalize_table(name, df):
    df = df.copy()

    if name in ID_COLUMNS:
        df = normalize_ids(df, ID_COLUMNS[name])

    if name in DATE_COLUMNS:
        df = normalize_dates(df, DATE_COLUMNS[name])

    if name in LOWER_COLUMNS:
        df = normalize_text(df, LOWER_COLUMNS[name])

    df = normalize_numeric(df)

    if name == "financial_profiles":
        df = normalize_profiles(df)

    if name in ["requests", "sample_requests"]:
        df = normalize_requests(df)

    return df


def normalize_all(data):
    normalized = {}

    for name, df in data.items():
        normalized[name] = normalize_table(name, df)

    return normalized