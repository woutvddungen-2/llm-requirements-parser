# Enhanced Testing Features

## Multi-Strategy Testing

You can now test multiple PDF extraction strategies in a single command, just like you can with multiple models.

### Before (multiple commands):
```bash
# Had to run 3 separate commands to test all strategies
pytest tests/test_expected_output.py --models anthropic:claude-sonnet-4-6 --pdf-strategy toc -k 051
pytest tests/test_expected_output.py --models anthropic:claude-sonnet-4-6 --pdf-strategy keyword -k 051
pytest tests/test_expected_output.py --models anthropic:claude-sonnet-4-6 --pdf-strategy regex -k 051
```

### After (single command):
```bash
# All strategies tested in one command with parallel execution
pytest tests/test_expected_output.py \
  --models anthropic:claude-sonnet-4-6 \
  --pdf-strategy toc,keyword,regex \
  -k 051 \
  -n auto
```

## CLI Flags Reference

### `--models`
Comma-separated list of models to test. Format: `vendor:model_name`

Examples:
- `--models anthropic:claude-sonnet-4-6`
- `--models anthropic:claude-sonnet-4-6,anthropic:claude-haiku-4-5-20251001`
- `--models deepseek:deepseek-chat,anthropic:claude-sonnet-4-6`

### `--use-few-shot`
Control few-shot prompt behavior:
- `false` (default): No few-shot examples
- `true`: Include few-shot examples
- `both`: Test both variants (parametrized)

### `--pdf-strategy`
Control PDF content extraction strategy (now supports multiple values):
- `toc` - Extract based on table of contents
- `keyword` - Extract based on keyword scoring
- `regex` - Extract based on regex pattern matching
- `llm` - Use an LLM to select relevant pages

Examples:
- `--pdf-strategy toc`
- `--pdf-strategy toc,keyword,regex` (all three)
- `--pdf-strategy keyword,llm` (two strategies)

### `--count`
Run each test N times for stability analysis:
- `--count 1` - Single run (default)
- `--count 3` - Three runs
- `--count 5` - Five runs (useful for flaky test detection)

### `-n auto`
Use pytest-xdist for parallel execution:
- `-n auto` - Use all available CPU cores
- `-n 4` - Use exactly 4 workers

### `-k`
Filter tests by name pattern:
- `-k 051` - Run only test 051
- `-k "051 or 052"` - Run tests 051 or 052
- `-k fietsenstalling` - Run any test with "fietsenstalling" in the name

## Practical Examples

### Example 1: Quick single test
```bash
pytest tests/test_expected_output.py \
  --models anthropic:claude-sonnet-4-6 \
  --pdf-strategy keyword \
  -k 051
```

### Example 2: Comprehensive model comparison
```bash
pytest tests/test_expected_output.py \
  --models anthropic:claude-sonnet-4-6,anthropic:claude-haiku-4-5-20251001,deepseek:deepseek-chat \
  --pdf-strategy toc,keyword \
  --count 3 \
  -n auto
```

### Example 3: Stability testing (detect flaky tests)
```bash
pytest tests/test_expected_output.py \
  --models anthropic:claude-sonnet-4-6 \
  --pdf-strategy keyword \
  -k 051 \
  --count 5 \
  -n auto
```

### Example 4: Full matrix testing
```bash
pytest tests/test_expected_output.py \
  --models anthropic:claude-sonnet-4-6,anthropic:claude-haiku-4-5-20251001 \
  --use-few-shot both \
  --pdf-strategy toc,keyword,regex \
  -k "051 or 052" \
  --count 2 \
  -n auto
```
This runs: 2 models × 2 few-shot variants × 3 strategies × 2 test cases × 2 counts = **96 tests total** in parallel!

## Environment Configuration

### Logging Directory
Set via environment variable (in `.env`):
```
LLM_LOGS_DIR=/mnt/c/datasets/enginize_root/LLM-outputs
```

The `load_dotenv()` in conftest.py automatically loads this on test startup.

### Logs Location
By default: `tests/logs/`
With env var: `/mnt/c/datasets/enginize_root/LLM-outputs/`

Each test run generates:
- `{timestamp}_results.jsonl` - All test results
- `{timestamp}_failures.jsonl` - Failed tests with diffs

## Performance Tips

1. **Use `-n auto`** for parallel execution - dramatically speeds up multiple test runs
2. **Use `--count N`** to detect flaky tests - run 3-5 times
3. **Use `-k` pattern** to filter tests - avoid running everything if not needed
4. **Batch related tests** - run similar configurations together for better cache utilization
5. **Monitor logs** - check `/mnt/c/datasets/enginize_root/LLM-outputs/` for detailed results
