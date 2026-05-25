# Copilot Instructions for Congressional Stock Tracker

## Build, Test, and Lint

**Requirements:**
```bash
pip3 install -r requirements.txt
```

**Run all tests:**
```bash
python3 -m unittest discover -s tests
```

**Run specific test:**
```bash
python3 -m unittest tests.test_data_fetcher.TestNormalization.test_normalize_trade_data
```

**No linter is configured.** Code style follows PEP 8 implicitly; focus on consistency with existing modules.

## High-Level Architecture

The application follows a **modular pipeline architecture**:

```
CLI Entry (congress_stock_tracker.py)
    ↓
    ├─→ CongressPromptAgent (ai_agent.py)
    │    └─→ Routes natural language to commands
    │
    ├─→ CongressStockTracker (congress_stock_tracker.py)
    │    ├─→ SQLite database operations
    │    ├─→ Member/trade management
    │    └─→ Query, export, report generation
    │
    ├─→ CongressDataFetcher (data_fetcher.py)
    │    ├─→ API clients (CapitolExposed, OpenSecrets)
    │    ├─→ File-based HTTP cache with TTL
    │    ├─→ Rate limiting
    │    ├─→ Trade normalization & deduplication
    │    └─→ Database import pipeline
    │
    ├─→ CLI Display (cli_display.py)
    │    ├─→ Rich tables (colored trade types)
    │    ├─→ Member dashboards
    │    ├─→ plotext bar charts
    │    └─→ Interactive terminal app menu
    │
    └─→ Analysis Tools (analysis_tools.py)
         └─→ Top traders, stocks, sectors, party breakdowns
```

**Key dataflow:**
1. User runs CLI command
2. CongressPromptAgent parses natural language into command structure
3. CongressStockTracker executes command (database operations)
4. CongressDataFetcher handles live data fetching (calls external APIs, caches results)
5. Data is normalized, deduplicated, and inserted into SQLite
6. CLI Display formats results for terminal output

## Key Conventions

### Date Handling

- **Internal storage:** ISO 8601 format (`YYYY-MM-DD`)
- **User-facing display:** `D Month YYYY` format (e.g., `16 January 2026`)
- **Parsing:** `parse_user_date()` accepts multiple formats and returns ISO date for queries
- **Formatting:** `format_display_date()` converts ISO to display format
- Use `with_display_dates()` to format entire trade rows for output

**Example:**
```python
# Parse user input
iso_date = parse_user_date("16 January 2026")  # → "2026-01-16"

# Format for display
display = format_display_date(iso_date)  # → "16 January 2026"

# Format a row
trade_row = {"trade_date": "2026-01-16", ...}
formatted = with_display_dates(trade_row)
```

### Trade Types

- **Canonical forms:** `"buy"`, `"sell"`, `"hold"`
- **API variants (normalized by data_fetcher):**
  - `"purchase"` → `"buy"`
  - `"sale"` → `"sell"`
  - `"exchange"` → `"hold"`
- Store as lowercase strings in database
- Use `TradeType` enum for type hints

### Caching Strategy

- **Location:** `.cache/` directory (file-based)
- **TTL:** Configurable per fetcher instance; default 3600 seconds (1 hour)
- **Cache key:** MD5 hash of `{source}:{identifier}` → `source_<hash>.json`
- **Payload structure:** `{"cached_at": "ISO timestamp", "data": <payload>}` or `{"cached_at": "...", "trades": [...]}`
- **Expiry:** Checked on read via `time.time() - file.st_mtime`
- **CLI interaction:** Use `--refresh` flag to bypass cache

**Example:**
```python
fetcher = CongressDataFetcher(cache_dir=".cache", cache_ttl=3600)
cache_path = fetcher._cache_key("capitolexposed", "nancy-pelosi")
cached_data = fetcher._read_cache(cache_path)  # Returns None if expired
```

### Deduplication & Uniqueness

- **Database constraint:** `UNIQUE(member_id, symbol, trade_date, trade_type)`
- **Insert strategy:** `INSERT OR IGNORE` (silently skips duplicates)
- **Deduplication in pipeline:** `CongressDataFetcher.deduplicate_trades()` removes duplicates before insert
- **Dedup key:** `(member_name, symbol, trade_date, trade_type)`

### Database Access Patterns

- **Row factory:** Always use `conn.row_factory = sqlite3.Row` for dict-like access to rows
- **Connection management:** Open and close connections within each method (not cached)
- **Parameterized queries:** Always use `?` placeholders to prevent SQL injection
- **Index-optimized queries:** Indexes exist on `(member_id, financial_year)`, `symbol`, `trade_date`, `trade_type`

**Example:**
```python
conn = sqlite3.connect(self.db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM trades WHERE member_id = ? AND financial_year = ?", (member_id, year))
rows = [dict(row) for row in cursor.fetchall()]
conn.close()
```

### API Integration

- **HTTP client:** Native `urllib` (no requests library in core; requests in data_fetcher.py for specific APIs)
- **Rate limiting:** `RateLimiter` class with configurable `min_interval`
- **SSL context:** Custom SSL with certifi bundle (handles macOS path issues)
- **Error handling:** Return `None` on parse/network errors; log warnings
- **Ticker normalization:** Convert to uppercase; validate length (2-5 chars)
- **Date parsing from APIs:** Strip time component; validate format

### Testing Patterns

- **Framework:** `unittest` with `mock.patch()` for API mocking
- **Test organization:** Group by concern (normalization, parsing, sync behavior)
- **Mock setup:** Use `@patch.object(CongressDataFetcher, "_http_get_json")` to intercept HTTP calls
- **Fixtures:** Use `setUp()` to initialize fetcher with `.cache_test` directory
- **Cleanup:** Call `fetcher.clear_cache()` in tests that write cache files

**Example:**
```python
class TestCapitolExposedMock(unittest.TestCase):
    def setUp(self):
        self.fetcher = CongressDataFetcher(cache_dir=".cache_test")
        self.fetcher.clear_cache()
    
    @patch.object(CongressDataFetcher, "_http_get_json")
    def test_fetch_capitolexposed_member(self, mock_get):
        mock_get.return_value = {"status": "success", "data": [...]}
        result = self.fetcher.fetch_capitolexposed_member("nancy-pelosi")
        self.assertIsNotNone(result)
```

### Logging

- **Logger setup:** `logger = logging.getLogger(__name__)` in each module
- **Levels used:**
  - `logger.debug()` for cache hits/misses, parsed data
  - `logger.info()` for major operations (sync complete, import count)
  - `logger.warning()` for skipped/invalid data, cache failures
  - `logger.error()` for database errors, API failures
- **Enable:** Pass `-v` or `--verbose` flag to CLI for debug output

### Error Handling

- **Graceful degradation:** Return `None` or empty list on parse errors; don't raise
- **Database errors:** Catch `sqlite3.Error`, log, return `False` or empty
- **Network errors:** Catch `urllib.error.URLError`, log, fall through to cache or return `None`
- **JSON parse errors:** Catch `json.JSONDecodeError`, log, treat as invalid cache

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENSECRETS_API_KEY` | OpenSecrets API authentication | (empty) |
| `CONGRESS_API_KEY` | Congress.gov API authentication | (empty) |
| `CAPITOL_MAX_PAGES` | Max pages for bulk CapitolExposed fetches | `5` |
| `FETCH_INTERVAL_SEC` | Delay between HTTP requests (rate limiting) | `0.3` |

## Important Implementation Notes

- **Sample data path:** `congress_stock_tracker.py` defines `SAMPLE_DATA` as hardcoded fixture with 5 members and 12 trades
- **Pending features:** See `PENDING_IMPLEMENTATION.md` for roadmap (OpenSecrets live, SEC Form 4, Senate disclosures, etc.)
- **CLI framework:** Custom argument parsing (not Click or argparse framework); commands are methods on `CongressStockTracker`
- **Financial year:** Treated as calendar year (not fiscal year starting Oct 1)
- **Amount ranges:** Stored as strings like `"$1,001-$15,000"` (not numeric min/max)
- **Interactive app:** Driven by `cli_display.py` with Rich library; menu-driven flow with user input loops
