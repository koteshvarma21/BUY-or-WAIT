import sys
from pathlib import Path
from decimal import Decimal
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))

import loader
import normalizer
from currency import convert_amount, get_rate


def test_same_currency_conversion_returns_original_amount():
    data = loader.load_all()
    data = normalizer.normalize_all(data)
    rates = data['exchange_rates']
    amount = convert_amount(100, 'USD', 'USD', '2023-10-15', rates)
    assert amount == 100


def test_usd_to_idr_rates_from_supplied_dataset():
    data = loader.load_all()
    data = normalizer.normalize_all(data)
    rates = data['exchange_rates']
    amount = convert_amount(100, 'usd', 'IDR', '2023-10-15', rates)
    assert str(amount.quantize(Decimal('0.01')) if hasattr(amount, 'quantize') else amount) == '1583333.00'


def test_missing_required_exchange_rate_raises_clear_error():
    rates = pd.DataFrame({
        'rate_date': pd.to_datetime(['2023-10-15']),
        'from_currency': ['USD'],
        'to_currency': ['EUR'],
        'rate': [1.0],
    })
    with pytest.raises(ValueError, match='No exchange rate'):
        convert_amount(100, 'USD', 'IDR', '2023-10-15', rates)


def test_missing_amount_returns_none():
    data = loader.load_all()
    data = normalizer.normalize_all(data)
    rates = data['exchange_rates']
    assert convert_amount(pd.NA, 'USD', 'IDR', '2023-10-15', rates) is None


def test_currency_codes_case_insensitive_at_boundary():
    data = loader.load_all()
    data = normalizer.normalize_all(data)
    rates = data['exchange_rates']
    amount = convert_amount(100, 'usd', 'idr', '2023-10-15', rates)
    assert amount is not None
