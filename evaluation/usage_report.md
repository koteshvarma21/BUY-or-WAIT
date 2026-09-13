# Token Usage and Cost Report

## Final Full-Dataset Run

Run date: 2026-09-13

Command:

`python code/main.py`

The final run processed all 250 requests from `dataset/requests.csv` and generated `output.csv`.

The generated output contained:

* 250 rows
* 0 duplicate request IDs
* all required output columns

## AI Model Usage

The final submission run did not invoke an external language or vision model.

The runner checks for the required model configuration before invoking the message or image parsers. No model credentials were configured for the final run, so the deterministic no-model fallback path was used.

No unstructured financial evidence was fabricated.

### Message Model

Provider: Not invoked
Model: Not invoked
Model calls: 0
Input tokens: 0
Output tokens: 0
Total tokens: 0
Estimated cost: $0.00

### Vision Model

Provider: Not invoked
Model: Not invoked
Model calls: 0
Input tokens: 0
Output tokens: 0
Total tokens: 0
Estimated cost: $0.00

## Overall Usage

Requests processed: 250
Total model calls: 0
Total input tokens: 0
Total output tokens: 0
Total tokens: 0
Average tokens per request: 0
Estimated total cost: $0.00
Estimated cost per request: $0.00

## Final Verification

The full automated test suite passed:

`90 passed`

The final output columns were:

* request_id
* amount_safe_to_pay
* affordability_status
* recommended_payment_method
* payment_plan
* earliest_date_for_full_payment
* spending_changes_needed
* decision_explanation

## Reproducibility

Financial-state construction, forecasting, safe-payment calculation, candidate generation, ranking, fallback explanation generation, and final validation were performed using deterministic Python logic.

No API keys, credentials, tokens, or other sensitive configuration values are included in this report.
