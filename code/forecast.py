from decimal import Decimal
import pandas as pd

from currency import convert_amount


def dec(value):
    if value is None or pd.isna(value):
        return None

    return Decimal(str(value))


def event_amount_home(event, home_currency, rates):
    amount = event.get("amount")

    if pd.isna(amount):
        return None

    currency = str(event["currency"]).upper()

    date = event.get("settlement_date")

    if pd.isna(date):
        date = event.get("event_date")

    if currency == home_currency:
        return dec(amount)

    return convert_amount(
        amount,
        currency,
        home_currency,
        date,
        rates
    )


def _schedule_type(dates):
    if len(dates) < 2:
        return None

    dates = sorted(pd.Timestamp(x) for x in dates)

    gaps = []

    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i - 1]).days
        gaps.append(gap)

    gaps = gaps[-8:]

    if not gaps:
        return None

    median_gap = int(round(pd.Series(gaps).median()))

    monthly_count = sum(
        1
        for gap in gaps
        if 28 <= gap <= 31
    )

    monthly_ratio = monthly_count / len(gaps)

    if (
        28 <= median_gap <= 31
        and monthly_ratio >= 0.60
    ):
        return {
            "type": "monthly",
            "days": None
        }

    allowed = {
        5,
        7,
        10,
        14,
        15,
        21
    }

    if median_gap not in allowed:
        return None

    close = sum(
        1
        for gap in gaps
        if abs(gap - median_gap) <= 2
    )

    consistency = close / len(gaps)

    if consistency < 0.65:
        return None

    return {
        "type": "days",
        "days": median_gap
    }


def _next_date(date, schedule):
    date = pd.Timestamp(date)

    if schedule["type"] == "monthly":
        return date + pd.DateOffset(months=1)

    return date + pd.Timedelta(
        days=schedule["days"]
    )


def _series_active(
    last_date,
    request_date,
    schedule
):
    gap = (
        request_date
        - pd.Timestamp(last_date)
    ).days

    if gap < 0:
        return True

    if schedule["type"] == "monthly":
        return gap <= 45

    return gap <= max(
        10,
        int(schedule["days"] * 1.7)
    )


def _mean_home_amount(
    rows,
    home_currency,
    rates,
    count=6
):
    values = []

    rows = rows.sort_values(
        "event_date"
    ).tail(count)

    for _, row in rows.iterrows():
        value = event_amount_home(
            row,
            home_currency,
            rates
        )

        if value is not None:
            values.append(value)

    if not values:
        return None

    return (
        sum(values)
        / Decimal(len(values))
    )


def _explicit_cashflows(state, data):
    events = state["all_events"]
    rates = data["exchange_rates"]

    request_date = state["request_date"]
    forecast_end = state["forecast_end"]
    home_currency = state["home_currency"]

    result = []
    unresolved = []

    superseded = set(
        events[
            events["linked_event_id"].notna()
            & (
                events["event_date"]
                <= request_date
            )
        ]["linked_event_id"]
        .dropna()
        .tolist()
    )

    for _, event in events.iterrows():
        event_id = event["event_id"]

        if event_id in superseded:
            continue

        status = str(
            event["status"]
        ).lower()

        direction = str(
            event["direction"]
        ).lower()

        settlement = event[
            "settlement_date"
        ]

        if pd.isna(settlement):
            settlement = event[
                "event_date"
            ]

        settlement = pd.Timestamp(
            settlement
        ).normalize()

        if (
            settlement < request_date
            or settlement > forecast_end
        ):
            continue

        if status in {
            "failed",
            "cancelled",
            "unrealized"
        }:
            continue

        if (
            status == "pending"
            and direction == "credit"
        ):
            continue

        if status not in {
            "pending",
            "scheduled"
        }:
            continue

        amount = event_amount_home(
            event,
            home_currency,
            rates
        )

        if amount is None:
            unresolved.append(
                event_id
            )
            continue

        result.append({
            "date": settlement,
            "direction": direction,
            "amount": amount,
            "category": event[
                "category"
            ],
            "event_id": event_id,
            "source": "explicit"
        })

    return result, unresolved


def _recurring_expenses(
    state,
    data
):
    events = state["all_events"]
    rates = data["exchange_rates"]

    request_date = state[
        "request_date"
    ]

    forecast_end = state[
        "forecast_end"
    ]

    home_currency = state[
        "home_currency"
    ]

    history = events[
        (events["status"] == "settled")
        & (
            events["direction"]
            == "debit"
        )
        & (
            events["event_date"]
            <= request_date
        )
        & events["amount"].notna()
    ].copy()

    result = []

    group_columns = [
        "event_type",
        "category",
        "flexibility"
    ]

    for key, rows in history.groupby(
        group_columns,
        dropna=False
    ):
        rows = rows.sort_values(
            "event_date"
        )

        if len(rows) < 4:
            continue

        dates = rows[
            "event_date"
        ].tolist()

        schedule = _schedule_type(
            dates
        )

        if schedule is None:
            continue

        last_date = pd.Timestamp(
            dates[-1]
        )

        if not _series_active(
            last_date,
            request_date,
            schedule
        ):
            continue

        amount = _mean_home_amount(
            rows,
            home_currency,
            rates
        )

        if amount is None:
            continue

        date = last_date

        while True:
            date = _next_date(
                date,
                schedule
            )

            if date > forecast_end:
                break

            if date < request_date:
                continue

            result.append({
                "date": pd.Timestamp(
                    date
                ).normalize(),
                "direction": "debit",
                "amount": amount,
                "category": key[1],
                "event_id": None,
                "source": "recurring"
            })

    return result


def _salary_rows(events):
    rows = events[
        (
            events["category"]
            == "salary"
        )
        & (
            events["direction"]
            == "credit"
        )
    ].copy()

    if rows.empty:
        return rows

    text = (
        rows["description"]
        .fillna("")
        .str.lower()
    )

    mask = (
        text.str.contains("salary")
        | text.str.contains("payroll")
        | text.str.contains(
            "base salary"
        )
    )

    return rows[
        mask
    ].copy()


def _recurring_income(
    state,
    data
):
    events = state["all_events"]
    rates = data["exchange_rates"]

    request_date = state[
        "request_date"
    ]

    forecast_end = state[
        "forecast_end"
    ]

    home_currency = state[
        "home_currency"
    ]

    rows = _salary_rows(
        events
    )

    settled = rows[
        (
            rows["status"]
            == "settled"
        )
        & (
            rows["event_date"]
            <= request_date
        )
        & rows["amount"].notna()
    ].copy()

    scheduled = rows[
        (
            rows["status"]
            == "scheduled"
        )
        & rows["amount"].notna()
        & (
            rows[
                "settlement_date"
            ]
            >= request_date
        )
    ].copy()

    dates = []
    amounts = []

    for _, row in settled.iterrows():
        amount = event_amount_home(
            row,
            home_currency,
            rates
        )

        if amount is None:
            continue

        dates.append(
            pd.Timestamp(
                row["event_date"]
            ).normalize()
        )

        amounts.append(
            amount
        )

    for _, row in scheduled.iterrows():
        amount = event_amount_home(
            row,
            home_currency,
            rates
        )

        if amount is None:
            continue

        dates.append(
            pd.Timestamp(
                row[
                    "settlement_date"
                ]
            ).normalize()
        )

        amounts.append(
            amount
        )

    if len(dates) < 2:
        return []

    order = sorted(
        range(len(dates)),
        key=lambda i: dates[i]
    )

    dates = [
        dates[i]
        for i in order
    ]

    amounts = [
        amounts[i]
        for i in order
    ]

    schedule = _schedule_type(
        dates
    )

    if schedule is None:
        return []

    if not _series_active(
        dates[-1],
        request_date,
        schedule
    ):
        return []

    if not scheduled.empty:
        amount = amounts[-1]

    else:
        recent = amounts[-4:]

        amount = (
            sum(recent)
            / Decimal(
                len(recent)
            )
        )

    result = []

    date = dates[-1]

    while True:
        date = _next_date(
            date,
            schedule
        )

        if date > forecast_end:
            break

        if date < request_date:
            continue

        result.append({
            "date": pd.Timestamp(
                date
            ).normalize(),
            "direction": "credit",
            "amount": amount,
            "category": "salary",
            "event_id": None,
            "source": "recurring"
        })

    return result


def _remove_recurring_duplicates(
    recurring,
    explicit
):
    clean = []

    for flow in recurring:
        duplicate = False

        for known in explicit:
            if (
                flow["direction"]
                == known["direction"]
                and flow["category"]
                == known["category"]
            ):
                gap = abs(
                    (
                        flow["date"]
                        - known["date"]
                    ).days
                )

                if gap <= 3:
                    duplicate = True
                    break

        if not duplicate:
            clean.append(
                flow
            )

    return clean


def build_cashflows(
    state,
    data
):
    explicit, unresolved = (
        _explicit_cashflows(
            state,
            data
        )
    )

    recurring_expenses = (
        _recurring_expenses(
            state,
            data
        )
    )

    recurring_income = (
        _recurring_income(
            state,
            data
        )
    )

    recurring = (
        recurring_expenses
        + recurring_income
    )

    recurring = (
        _remove_recurring_duplicates(
            recurring,
            explicit
        )
    )

    flows = (
        explicit
        + recurring
    )

    return (
        flows,
        unresolved
    )


def simulate_forecast(
    state,
    data,
    extra_payments=None
):
    flows, unresolved = (
        build_cashflows(
            state,
            data
        )
    )

    if extra_payments is None:
        extra_payments = []

    for payment in extra_payments:
        amount = dec(
            payment["amount"]
        )

        if amount is None:
            continue

        flows.append({
            "date": pd.Timestamp(
                payment["date"]
            ).normalize(),
            "direction": "debit",
            "amount": amount,
            "category":
                "request_payment",
            "event_id": None,
            "source":
                payment.get(
                    "source",
                    "request"
                )
        })

    flows.sort(
        key=lambda x: (
            x["date"],
            0
            if x["direction"]
            == "debit"
            else 1
        )
    )

    balance = state[
        "current_balance"
    ]

    minimum_balance = state[
        "minimum_balance"
    ]

    if balance is None:
        raise ValueError(
            "Current balance is missing"
        )

    if minimum_balance is None:
        raise ValueError(
            "Minimum balance is missing"
        )

    lowest_balance = balance

    rows = [{
        "date":
            state["request_date"],
        "direction":
            "opening",
        "amount":
            Decimal("0"),
        "category":
            "opening_balance",
        "event_id":
            None,
        "source":
            "profile",
        "balance":
            balance
    }]

    for flow in flows:

        if (
            flow["date"]
            < state["request_date"]
        ):
            continue

        if (
            flow["date"]
            > state["forecast_end"]
        ):
            continue

        amount = flow[
            "amount"
        ]

        if amount is None:
            continue

        if (
            flow["direction"]
            == "credit"
        ):
            balance += amount

        elif (
            flow["direction"]
            == "debit"
        ):
            balance -= amount

        else:
            continue

        if balance < lowest_balance:
            lowest_balance = balance

        rows.append({
            "date":
                flow["date"],
            "direction":
                flow["direction"],
            "amount":
                amount,
            "category":
                flow["category"],
            "event_id":
                flow.get(
                    "event_id"
                ),
            "source":
                flow["source"],
            "balance":
                balance
        })

    timeline = pd.DataFrame(
        rows
    )

    return {
        "timeline":
            timeline,

        "ending_balance":
            balance,

        "minimum_projected_balance":
            lowest_balance,

        "required_minimum_balance":
            minimum_balance,

        "is_safe":
            (
                lowest_balance
                >= minimum_balance
            ),

        "unresolved_event_ids":
            unresolved,

        "cashflow_count":
            len(rows) - 1
    }