# Export Test Results to Excel

Simple tool to export test logs to CSV for analysis in Excel.

## Quick Start

```bash
python3 export_logs.py
```

1. **File picker opens** → Select one or more `.jsonl` log files from `tests/logs/`
2. **Directory picker opens** → Choose where to save the CSV file
3. **Done** → CSV file ready to open in Excel

## What You Get

A CSV file with these columns:

| Column | Example |
|--------|---------|
| timestamp | 2026-05-26T06:38:40.298449+00:00 |
| run_id | 2026-05-26T06-38-32Z |
| case | 051_real_test_1 |
| model | anthropic:claude-sonnet-4-6 |
| use_few_shot | False |
| source_mode | page_finder |
| page_finder_strategy | keyword |
| page_selection_method | Keyword scoring |
| selected_pages | 44,202,203,204 |
| passed | True |
| pdf_extraction_ms | 2714 |
| duration_ms | 4393 |
| few_shot_setup_ms | 0 |
| total_duration_ms | 4397 |
| input_tokens | 29356 |
| output_tokens | 120 |
| error | (empty if test passed) |

## In Excel

Import the CSV and use Excel's built-in tools:
- **Pivot tables** for summaries by model/case
- **Charts** for visualization
- **Filters** for analysis
- **Formulas** for custom calculations

No Python needed after export.

## Log Files Location

Test results are saved automatically to: `tests/logs/`

File names: `{TIMESTAMP}_results.jsonl` (e.g., `2026-05-26T06-38-32Z_results.jsonl`)

New log file created each time you run tests:
```bash
pytest tests/ --models anthropic --use-few-shot both -v
```
