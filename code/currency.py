from decimal import Decimal
import pandas as pd


def get_rate(rates, date, from_cur, to_cur):
    from_cur = str(from_cur).upper()
    to_cur = str(to_cur).upper()

    if from_cur == to_cur:
        return Decimal("1")

    date = pd.Timestamp(date).normalize()

    match = rates[
        (rates["rate_date"].dt.normalize() == date)
        & (rates["from_currency"] == from_cur)
        & (rates["to_currency"] == to_cur)
    ]

    if match.empty:
        raise ValueError(
            f"No exchange rate for "
            f"{date.date()} {from_cur}->{to_cur}"
        )

    rate = match.iloc[0]["rate"]

    return Decimal(str(rate))


def convert_amount(
    amount,
    from_cur,
    to_cur,
    date,
    rates
):
    if pd.isna(amount):
        return None

    amount = Decimal(str(amount))

    rate = get_rate(
        rates,
        date,
        from_cur,
        to_cur
    )

    return amount * rate