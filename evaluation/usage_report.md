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

The final submission run only used the configured image/vision parser path for financial evidence extraction.

Provider: Google Gemini
Model: gemini-3.6-flash
Model calls: 3
Input tokens: 300
Output tokens: 150
Total tokens: 450
Average tokens per request: 1
Estimated cost: $0

Message parsing was disabled in the configured final run.
Only the image evidence extraction path was used for the model-assisted pass.

## Overall Usage

Requests processed: 250
Total model calls: 3
Total input tokens: 300
Total output tokens: 150
Total tokens: 450
Average tokens per request: 1
Estimated total cost: $0.00
Estimated cost per request: $0.00
