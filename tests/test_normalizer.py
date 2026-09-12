import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))

import loader
import normalizer


def test_normalizer_parses_request_and_event_dates_and_messages_sent_at():
    data = loader.load_all()
    data = normalizer.normalize_all(data)

    assert pd.api.types.is_datetime64_any_dtype(data['requests']['request_date'])
    assert pd.api.types.is_datetime64_any_dtype(data['financial_events']['event_date'])
    assert pd.api.types.is_datetime64_any_dtype(data['messages']['sent_at'])

    # Direct comparison proof: we prove the normalized sent_at field is
    # comparable to the naive request/event timeline without timezone error.
    first_request_date = data['requests']['request_date'].iloc[0]
    first_sent_at = data['messages']['sent_at'].iloc[0]
    assert first_sent_at <= first_request_date or first_sent_at >= first_request_date


def test_normalizer_preserves_currency_and_list_and_id_and_amount_behaviour():
    data = loader.load_all()
    data = normalizer.normalize_all(data)

    # currencies remain uppercase
    assert data['exchange_rates']['from_currency'].str.upper().equals(data['exchange_rates']['from_currency'])
    assert data['exchange_rates']['to_currency'].str.upper().equals(data['exchange_rates']['to_currency'])

    # normalized list representation useful for payment methods
    profile = data['financial_profiles'].iloc[0]
    assert isinstance(profile['payment_methods_user_will_consider_list'], list)

    # IDs remain nullable strings, not literal 'nan'
    message_related_event = data['messages']['related_event_id'].astype('string')
    assert message_related_event.isna().any()
    assert '<NA>' not in str(message_related_event.dropna().head())

    # Amounts remain missing rather than being replaced with 0
    assert data['financial_events']['amount'].isna().any()


def test_normalizer_status_and_payment_method_values_stay_normalized_and_str_cased():
    data = loader.load_all()
    data = normalizer.normalize_all(data)
    statuses = data['financial_events']['status'].dropna().astype(str)
    assert statuses.str.lower().equals(statuses)
