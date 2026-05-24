# Congressional Stock Trading Tracker

A Python CLI for collecting, storing, searching, and analyzing publicly reported stock transactions by members of the US Congress.

The tracker stores trades in SQLite, supports both sample and live data imports, and can display reports as plain text or Rich-powered terminal tables and charts.

## Features

- Track buy, sell, and hold transactions by member, stock, date, and financial year.
- Import sample data for local exploration.
- Fetch live House PTR data through the CapitolExposed API integration.
- Sync congressional member roster data before importing trades.
- Search trades by member, company, ticker, type, date range, and year.
- Generate member reports, yearly statistics, CSV exports, and JSON exports.
- Use an interactive terminal app with Rich tables and plotext charts.
- Run focused unit tests for data normalization, API parsing, roster sync, and member import behavior.

## Project Status

The core CLI, SQLite schema, sample data, CapitolExposed live import path, roster sync, caching, deduplication, and basic analysis tools are implemented.

Some source integrations are still planned or partial:

- OpenSecrets support exists as a stub and requires `OPENSECRETS_API_KEY`.
- SEC Form 4, Senate disclosures, and direct House/Senate disclosure parsers are still pending.
- See `PENDING_IMPLEMENTATION.md` for the current implementation tracker.

## Requirements

- Python 3.7+
- SQLite3, included with Python
- Python packages from `requirements.txt`

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Quick Start

```bash
cd "/Users/shaileshyadav/Desktop/AI agent"

# Load sample data into congress_stocks.db
python3 congress_stock_tracker.py init

# Show yearly stats
python3 congress_stock_tracker.py stats

# Open the interactive terminal UI
python3 congress_stock_tracker.py app
```

Running the script with no subcommand also launches the interactive app when Rich is available:

```bash
python3 congress_stock_tracker.py
```

Use `--plain` when you want text-only output:

```bash
python3 congress_stock_tracker.py --plain stats
```

## Common Workflows

### View a Member Report

```bash
python3 congress_stock_tracker.py report --member "Nancy Pelosi"
python3 congress_stock_tracker.py report --member "Nancy Pelosi" --format json
python3 congress_stock_tracker.py report --all --year 2024
```

### Search and Filter Trades

```bash
# Search member, company, or symbol
python3 congress_stock_tracker.py search -q NVDA

# Filter by member, type, and year
python3 congress_stock_tracker.py trades --member "Nancy Pelosi" --type buy --year 2024

# Filter by stock and paginate
python3 congress_stock_tracker.py trades --stock AAPL --limit 25 --offset 25

# Search by date range
python3 congress_stock_tracker.py search --from "1 January 2024" --to "31 December 2024" --sort-by amount
```

### Export Data

```bash
# Export all trades to congress_trades_export.csv
python3 congress_stock_tracker.py export

# Export JSON with filters
python3 congress_stock_tracker.py export --format json --output pelosi_2024 --member "Nancy Pelosi" --year 2024

# Export selected fields only
python3 congress_stock_tracker.py export --fields member_name,symbol,trade_type,trade_date,amount_range
```

### Fetch Live Data

```bash
# Default live source: CapitolExposed
python3 congress_stock_tracker.py update

# Refresh cache and limit API pages
python3 congress_stock_tracker.py update --refresh --pages 2

# Update one or more members
python3 congress_stock_tracker.py update --member "Ro Khanna" --member "Nancy Pelosi"

# Try all configured sources
python3 congress_stock_tracker.py update --source all
```

By default, `update` syncs member data before importing trades. Use `--no-sync-members` to skip that step.

### Sync Members

```bash
# Sync in-office members with reported trades
python3 congress_stock_tracker.py sync-members --traders-only

# Include former members
python3 congress_stock_tracker.py sync-members --include-former
```

### Run Analysis

```bash
python3 analysis_tools.py
```

The analysis script reports top traders, commonly traded stocks, party and chamber breakdowns, and basic sector summaries.

## Command Reference

```bash
python3 congress_stock_tracker.py [-v] [--plain] <command>
```

| Command | Purpose |
| --- | --- |
| `app` | Launch the interactive terminal UI. |
| `init` | Initialize the database with sample data. Use `--force` to re-import samples. |
| `stats` | Show yearly statistics, with optional `--year`, `--party`, `--chamber`, and `--sort-by`. |
| `report` | Generate reports for `--member` or `--all`; supports `--format text\|json`. |
| `trades` | Look up trades by member, year, type, stock, sort order, limit, and offset. |
| `search` | Search member names, companies, symbols, trade types, years, and date ranges. |
| `export` | Export filtered data as CSV or JSON. |
| `update` | Fetch live data from configured public sources. |
| `sync-members` | Sync the member roster from CapitolExposed. |

Global options:

- `-v`, `--verbose`: enable debug logging.
- `--plain`: disable Rich tables and charts.

## Command Examples and Output

The examples below use `--plain` where possible so the output is easy to read in docs. Without `--plain`, commands render with Rich tables and terminal charts when dependencies are installed.

### `app`

Launches the interactive terminal UI:

```bash
python3 congress_stock_tracker.py app
```

Example display:

```text
╔════════════════════════════════════════════════════════════╗
║           Congressional Stock Trading Tracker             ║
║        CLI · Live PTR data · Terminal charts              ║
╚════════════════════════════════════════════════════════════╝

Menu  1 Member report  2 Search  3 Stats  4 Analysis
      5 Update  6 Sync  7 Export  8 Members  q Quit
Choice [1]:
```

### `init`

Creates the SQLite schema and loads sample members and trades:

```bash
python3 congress_stock_tracker.py init
```

Example output:

```text
✓ Imported 5 members and 12 trades

==============================================================================================================
  CONGRESSIONAL STOCK TRADING SUMMARY - ALL YEARS
==============================================================================================================

📅 Financial Year 2024
--------------------------------------------------------------------------------------------------------------
Member                         Party        Chamber  Buys   Sells  Holds  Total  Stocks
--------------------------------------------------------------------------------------------------------------
Nancy Pelosi                   Democratic   House    2      1      0      3      2
Kevin McCarthy                 Republican   House    2      1      0      3      2
```

### `stats`

Shows aggregated trading activity by member and financial year:

```bash
python3 congress_stock_tracker.py --plain stats --year 2024
```

Example output:

```text
==============================================================================================================
  CONGRESSIONAL STOCK TRADING SUMMARY - 2024
==============================================================================================================

📅 Financial Year 2024
--------------------------------------------------------------------------------------------------------------
Member                         Party        Chamber  Buys   Sells  Holds  Total  Stocks
--------------------------------------------------------------------------------------------------------------
Nancy Pelosi                   Democratic   House    10     6      0      16     7
Mitch McConnell                Republican   Senate   1      0      1      2      2
Kevin McCarthy                 Republican   House    2      1      0      3      2
--------------------------------------------------------------------------------------------------------------
YEAR TOTAL                                           17     8      3      28
```

### `report`

Prints a full member dashboard with yearly totals and transaction rows:

```bash
python3 congress_stock_tracker.py --plain report --member "Nancy Pelosi"
```

Example output:

```text
======================================================================
  NANCY PELOSI - DEMOCRATIC - HOUSE (CA)
======================================================================

📅 Financial Year 2026
----------------------------------------------------------------------
  Total Transactions: 5 | Buys: 5 | Sells: 0 | Holds: 0 | Unique Stocks: 5

  Transactions:
    📈 16 January 2026 | AB     AllianceBernstein Holding L.P. Units | BUY  | $1,000,001-$5,000,000
    📈 16 January 2026 | VST    Vistra Corp. Common Stock | BUY  | $100,001-$250,000
    📈 16 January 2026 | NVDA   NVIDIA Corporation - Common Stock | BUY  | $250,001-$500,000
```

JSON output is also available:

```bash
python3 congress_stock_tracker.py --plain report --member "Nancy Pelosi" --format json
```

Example output:

```json
{
  "member": {
    "member_id": "P000197",
    "name": "Nancy Pelosi",
    "party": "Democratic",
    "chamber": "House",
    "state": "CA"
  },
  "trades": [
    {
      "symbol": "NVDA",
      "trade_date": "16 January 2026",
      "trade_type": "buy",
      "amount_range": "$250,001-$500,000"
    }
  ]
}
```

### `trades`

Lists matching trades with pagination:

```bash
python3 congress_stock_tracker.py --plain trades --member "Nancy Pelosi" --limit 3
```

Example output:

```text
Trades for Nancy Pelosi (3 shown)
Date               Symbol   Company                Type   Amount           Member
----------------------------------------------------------------------------------------------------------
16 January 2026    GOOGL    Alphabet Inc. - Clas   BUY    $500,001-$1,000,000 Nancy Pelosi
16 January 2026    AMZN     Amazon.com, Inc. - C   BUY    $500,001-$1,000,000 Nancy Pelosi
16 January 2026    NVDA     NVIDIA Corporation -   BUY    $250,001-$500,000 Nancy Pelosi

Showing 3 of 40 (use --offset to paginate)
```

### `search`

Searches member names, companies, and symbols:

```bash
python3 congress_stock_tracker.py --plain search -q NVDA --limit 3
```

Example output:

```text
Search results (3 shown)
Date               Symbol   Company                Type   Amount           Member
----------------------------------------------------------------------------------------------------------
24 February 2026   NVDA     Nvidia Corporation     BUY    $1,001-$15,000   Ro Khanna
16 January 2026    NVDA     NVIDIA Corporation -   BUY    $250,001-$500,000 Nancy Pelosi
30 December 2025   NVDA     NVIDIA Corporation -   BUY    $100,001-$250,000 Nancy Pelosi

Showing 3 of 10 (use --offset to paginate)
```

### `export`

Writes filtered data to CSV or JSON:

```bash
python3 congress_stock_tracker.py export --format csv --output pelosi_trades --member "Nancy Pelosi"
```

Example output:

```text
✓ Exported 40 trades to pelosi_trades.csv
```

Example CSV rows:

```csv
member_name,symbol,trade_type,trade_date,amount_range
Nancy Pelosi,GOOGL,buy,16 January 2026,"$500,001-$1,000,000"
Nancy Pelosi,AMZN,buy,16 January 2026,"$500,001-$1,000,000"
```

### `update`

Fetches live trade data from configured public sources:

```bash
python3 congress_stock_tracker.py update --source capitolexposed --member "Nancy Pelosi" --pages 1
```

Example output:

```text
Updating from source(s): capitolexposed...
✓ Update complete — members: +0 new, 1 updated, 0 auto-added from trades | trades: fetched 40, imported 0, skipped 40, errors 0
```

### `sync-members`

Syncs member roster records before trade imports:

```bash
python3 congress_stock_tracker.py sync-members --traders-only
```

Example output:

```text
✓ Member sync complete — roster: 540, added: 22, updated: 18, skipped: 500 | DB members: 5 → 27
```

### `analysis_tools.py`

Runs the standalone analysis report:

```bash
python3 analysis_tools.py
```

Example output:

```text
================================================================================
  CONGRESSIONAL STOCK TRADING ANALYSIS REPORT
================================================================================

📊 TOP TRADERS (by transaction count)
--------------------------------------------------------------------------------
1. Ro Khanna                      159 trades (126 buy, 0 sell, 33 hold)
2. Nancy Pelosi                    19 trades (11 buy, 8 sell, 0 hold)

📈 MOST TRADED STOCKS
--------------------------------------------------------------------------------
1. NVDA   Nvidia                         10 trades (8 buy, 2 sell)
2. CART   Maplebear Inc                   8 trades (8 buy, 0 sell)
```

## Data Sources

Implemented:

- CapitolExposed API for House PTR trade data and roster data.

Planned or partial:

- OpenSecrets API, requiring `OPENSECRETS_API_KEY`.
- SEC EDGAR Form 4 parsing.
- Senate disclosure parsing.
- Direct House ethics disclosure parsing.
- Congress.gov member sync, requiring `CONGRESS_API_KEY`.

Environment variables:

| Variable | Purpose |
| --- | --- |
| `OPENSECRETS_API_KEY` | OpenSecrets API key. |
| `CONGRESS_API_KEY` | Congress.gov API key. |
| `CAPITOL_MAX_PAGES` | Default max pages for bulk CapitolExposed fetches. |
| `FETCH_INTERVAL_SEC` | Delay between HTTP requests. Default is `0.3`. |

## Database

The default SQLite database is `congress_stocks.db`.

Dates are displayed and exported as `DAY MONTH NAME YEAR`, for example `5 March 2024`. Internally, dates are stored as `YYYY-MM-DD` so filtering and sorting remain reliable.

Main tables:

- `members`: biographical and chamber data for members of Congress.
- `trades`: individual transactions with ticker, company, date, type, source, and amount range.
- `yearly_stats`: aggregated buy, sell, hold, total trade, and unique stock counts by member and year.

Inspect the database directly:

```bash
sqlite3 congress_stocks.db
```

Example SQL:

```sql
SELECT member_name, symbol, trade_type, trade_date, amount_range
FROM trades
WHERE financial_year = 2024
ORDER BY trade_date DESC;
```

## Sample Data

`python3 congress_stock_tracker.py init` loads demonstration records for:

- Nancy Pelosi
- Kevin McCarthy
- Chuck Schumer
- Mitch McConnell
- Alexandria Ocasio-Cortez

The sample set includes 12 2024 transactions across companies such as Microsoft, Apple, Tesla, Nvidia, JPMorgan, Google, Coca Cola, ExxonMobil, and ETFs.

## Testing

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Current tests cover normalization, deduplication, CapitolExposed parsing, roster conversion, roster sync, and member auto-add behavior.

## Project Layout

| File | Purpose |
| --- | --- |
| `congress_stock_tracker.py` | Main CLI, database access, reporting, imports, and exports. |
| `data_fetcher.py` | Public data source clients, caching, normalization, and update pipeline. |
| `analysis_tools.py` | Additional analytics for top traders, stocks, parties, chambers, and sectors. |
| `cli_display.py` | Rich and plotext terminal UI components. |
| `tests/test_data_fetcher.py` | Unit tests for data fetching and normalization behavior. |
| `QUICKSTART.md` | Shorter usage guide. |
| `PENDING_IMPLEMENTATION.md` | Implementation status and roadmap. |

## Adding Data Programmatically

```python
from congress_stock_tracker import CongressStockTracker, CongressMember, StockTrade

tracker = CongressStockTracker()

member = CongressMember(
    name="John Smith",
    party="Democratic",
    chamber="Senate",
    state="NY",
    member_id="S000123",
)
tracker.add_member(member)

trade = StockTrade(
    member_id="S000123",
    member_name="John Smith",
    symbol="MSFT",
    company="Microsoft",
    trade_date="2024-03-15",
    trade_type="buy",
    amount_range="$100K-$250K",
    financial_year=2024,
    source="sec.gov",
    filing_date="2024-03-20",
)
tracker.add_trade(trade)
tracker.update_yearly_stats()
```

## Notes and Disclaimer

- Congressional disclosure amounts are reported as ranges, not exact dollar values.
- The project treats financial year as calendar year.
- Live source availability and reporting delays vary by source.
- This tool is for educational and research purposes. Verify important information against official filings before relying on it.
