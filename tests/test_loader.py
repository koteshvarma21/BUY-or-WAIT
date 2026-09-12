import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))

import loader


def test_load_all_loads_every_expected_dataset():
    data = loader.load_all()
    assert set(data) == {
        'financial_profiles', 'financial_events', 'exchange_rates',
        'requests', 'sample_requests', 'request_payment_options',
        'messages', 'images', 'output'
    }


def test_dataset_counts_from_loader():
    data = loader.load_all()
    assert len(data['requests']) == 250
    assert len(data['financial_events']) == 25342


def test_required_columns_validation_succeeds_on_official_dataset():
    data = loader.load_all()
    for table, df in data.items():
        missing = loader.validate_required_columns(table, df)
        assert missing == []


def test_missing_required_columns_generates_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, 'DATASET_DIR', tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    # Create a full valid shape for every dataset except the intentionally
    # malformed requests data, so validation reaches the target file.
    table_columns = {
        'financial_profiles': [
            'user_id', 'home_currency', 'current_available_balance',
            'minimum_balance_to_keep', 'financial_priorities',
            'expense_categories_to_protect',
            'expense_categories_user_is_willing_to_reduce',
            'expense_categories_user_is_willing_to_stop',
            'payment_methods_user_will_consider', 'max_installment_months'
        ],
        'financial_events': [
            'event_id', 'user_id', 'event_type', 'description', 'category',
            'direction', 'amount', 'currency', 'event_date',
            'settlement_date', 'status', 'linked_event_id', 'flexibility',
            'minimum_allowed_amount'
        ],
        'exchange_rates': ['rate_date', 'from_currency', 'to_currency', 'rate'],
        'requests': [
            'request_id', 'user_id', 'request_date', 'request_type',
            'requested_amount', 'desired_completion_date',
            'allows_partial_payment', 'request_text'
        ],
        'sample_requests': [
            'request_id', 'user_id', 'request_date', 'request_type',
            'requested_amount', 'desired_completion_date',
            'allows_partial_payment', 'request_text', 'amount_safe_to_pay',
            'affordability_status', 'recommended_payment_method',
            'payment_plan', 'earliest_date_for_full_payment',
            'spending_changes_needed', 'decision_explanation'
        ],
        'request_payment_options': [
            'payment_option_id', 'request_id', 'payment_method',
            'payment_amount', 'number_of_payments', 'first_payment_date',
            'payment_frequency_days', 'financing_fee',
            'total_payable_amount'
        ],
        'messages': [
            'message_id', 'user_id', 'request_id', 'related_event_id',
            'sent_at', 'source_type', 'message_text'
        ],
        'images': ['image_id', 'user_id', 'request_id', 'related_event_id'],
        'output': [
            'request_id', 'amount_safe_to_pay', 'affordability_status',
            'recommended_payment_method', 'payment_plan',
            'earliest_date_for_full_payment', 'spending_changes_needed',
            'decision_explanation'
        ],
    }

    for name, cols in table_columns.items():
        pd.DataFrame(columns=cols).to_csv(tmp_path / f'{name}.csv', index=False)

    # Remove requested_amount from requests.csv to force the target error.
    pd.DataFrame(columns=[
        'request_id', 'user_id', 'request_date', 'request_type',
        'desired_completion_date', 'allows_partial_payment', 'request_text'
    ]).to_csv(tmp_path / 'requests.csv', index=False)

    with pytest.raises(ValueError, match='requests.csv is missing required columns'):
        loader.load_all()


def test_missing_file_raises_file_not_found_error(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, 'DATASET_DIR', tmp_path)
    with pytest.raises(FileNotFoundError):
        loader.load_csv('requests')
