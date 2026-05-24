# Congressional Stock Tracker — Implementation Tracker

**Last updated:** May 24, 2026  
**Overall progress:** ~65%

This file is the single source of truth for **what is done** vs **what remains**. Update it whenever features are implemented.

---

## ✅ Implemented

### CLI (`congress_stock_tracker.py`)
| Command | Status | Notes |
|---------|--------|-------|
| `init` | ✅ | Schema, sample data, `--force`, `-v` |
| `stats` | ✅ | `--year`, `--party`, `--chamber`, `--sort-by` |
| `report` | ✅ | `--member`, `--all`, `--format text\|json` |
| `trades` | ✅ | Filters, `--stock`, sort, pagination |
| `export` | ✅ | CSV/JSON, `--fields`, date/member filters |
| `search` | ✅ | `-q`, multi-filter, pagination |
| `update` | ✅ | `--source`, `--member`, `--refresh`, `--pages`, auto member sync |
| `sync-members` | ✅ | Roster sync from CapitolExposed API |
| `app` | ✅ | Interactive graphical CLI (Rich + plotext) |

### Data pipeline (`data_fetcher.py`)
| Feature | Status | Notes |
|---------|--------|-------|
| CapitolExposed live API | ✅ | House PTR trades via `capitolexposed` / `capitaltrades` / `house` |
| File-based HTTP cache | ✅ | `.cache/`, TTL, `--refresh` clears |
| Rate limiting | ✅ | `RateLimiter`, `FETCH_INTERVAL_SEC` env |
| Trade normalization | ✅ | Dates, tickers, buy/sell/hold mapping |
| Validation & dedup | ✅ | Date range, symbol required, dedup keys |
| `update_database()` | ✅ | Imports live trades into SQLite |
| Auto-add members from API roster | ✅ | `sync-members`, `update` pre-sync, trade-time `ensure_member` |
| OpenSecrets stub | ✅ | Needs `OPENSECRETS_API_KEY` |
| SSL (macOS) | ✅ | Uses `certifi` or `vendor/certifi` bundle |

### Database
| Feature | Status |
|---------|--------|
| Schema (members, trades, yearly_stats) | ✅ |
| Indexes on trades | ✅ |
| `INSERT OR IGNORE` dedup | ✅ |
| Yearly stats aggregation | ✅ |

### Analysis (`analysis_tools.py`)
| Feature | Status |
|---------|--------|
| Top traders / most traded stocks | ✅ |
| Party & chamber breakdown | ✅ |
| Sector analysis (hardcoded map) | ✅ |

### Tests
| Feature | Status |
|---------|--------|
| `tests/test_data_fetcher.py` | ✅ | 7 unit tests (normalization, mock API) |

### Graphical CLI (`cli_display.py`)
| Feature | Status |
|---------|--------|
| Rich tables (color-coded buy/sell/hold) | ✅ |
| Member dashboard (stats cards, bar charts) | ✅ |
| Interactive menu (`app` command) | ✅ |
| Terminal bar charts (plotext) | ✅ |
| Progress spinners on update/sync | ✅ |

### Verified live workflow
```bash
pip3 install -r requirements.txt
python3 congress_stock_tracker.py app                    # interactive GUI in terminal
python3 congress_stock_tracker.py report --member "Ro Khanna"
python3 congress_stock_tracker.py search -q Khanna
python3 congress_stock_tracker.py report --member "Ro Khanna" --plain   # old text mode
```

---

## ⏳ Pending

### 🔴 Critical — Live data (remaining sources)
| Task | Priority | Module |
|------|----------|--------|
| OpenSecrets live API (verify with real key) | High | `data_fetcher.py` |
| CapitalTrades.com direct scraper (optional; CapitolExposed covers House PTR) | Medium | `data_fetcher.py` |
| SEC EDGAR Form 4 XML parser | High | `data_fetcher.py` |
| Senate financial disclosure parser | High | `data_fetcher.py` |
| House ethics PDF parser (direct, non-API) | Low | `data_fetcher.py` |
| Congress.gov member sync (`CONGRESS_API_KEY`) | Medium | `data_fetcher.py` |

### 🟡 Important — CLI polish
| Task | Priority |
|------|----------|
| ~~Terminal colors for `stats` / tables~~ | Done (Rich) |
| PDF report export | Low |
| Excel (XLSX) export | Medium |
| Export progress bar for large datasets | Low |
| Advanced amount-range search (numeric min/max) | Medium |

### 🟡 Important — Data quality
| Task | Priority |
|------|----------|
| Ticker validation against market API | Medium |
| Fuzzy duplicate matching across sources | Medium |
| Member name alias / nickname handling | Medium |
| Amount range format validation | Low |

### 🟡 Important — Performance & ops
| Task | Priority |
|------|----------|
| Cache size limits & cleanup CLI | Medium |
| Exponential backoff on API errors | Medium |
| OpenSecrets daily request budget (100/day) | Medium |
| Batch insert for large imports | Medium |

### 🟢 Analysis & reporting
| Task | Priority |
|------|----------|
| Pattern detection (unusual trades, clusters) | Medium |
| Returns vs market benchmarks | Low |
| Time series / trends | Low |
| `reporting.py` — HTML/PDF reports | Medium |
| Charts (matplotlib/plotly) | Low |
| Web dashboard (FastAPI + UI) | Low |

### 🟢 Quality & deployment
| Task | Priority |
|------|----------|
| Integration tests (CLI end-to-end) | High |
| `config.yaml` + feature flags | Medium |
| Docker / docker-compose | Medium |
| GitHub Actions CI | Medium |
| Structured JSON logging | Low |
| DB migrations (Alembic/raw SQL) | Low |

### 🟢 Future features
| Task | Priority |
|------|----------|
| Alerts (email/Slack) | Low |
| User auth / API keys | Low |
| Committee & vote correlation tables | Low |

---

## 📊 Progress by category

| Category | Done | Pending | % |
|----------|------|---------|---|
| CLI commands | 7/7 commands | polish (colors, xlsx, pdf) | **90%** |
| Live data fetching | CapitolExposed | OpenSecrets, SEC, Senate, scrapers | **45%** |
| Normalization / validation | core pipeline | fuzzy match, ticker API | **70%** |
| Caching / rate limits | basic | backoff, cache purge | **60%** |
| Analysis tools | basic stats | patterns, returns | **35%** |
| Testing | unit tests | integration, CI | **20%** |
| Deployment | — | Docker, config | **0%** |
| **OVERALL** | | | **~65%** |

---

## 🎯 Current phase: Phase 2 (Live Data)

**Completed this session:**
- [x] CapitolExposed public API integration
- [x] Live `update` imports real House PTR trades
- [x] Member slug resolution (bioguide ID + name)
- [x] Rate limiter + SSL fix
- [x] Unit tests for fetcher

**Next up:**
1. SEC EDGAR Form 4 search for congressional insiders
3. Senate disclosure source
4. Integration tests + `config.yaml`

---

## 📝 Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENSECRETS_API_KEY` | OpenSecrets.org API |
| `CONGRESS_API_KEY` | Congress.gov member API |
| `CAPITOL_MAX_PAGES` | Max pages per bulk fetch (default: 5) |
| `FETCH_INTERVAL_SEC` | Seconds between HTTP requests (default: 0.3) |

---

## 🔗 Related files

- [congress_stock_tracker.py](congress_stock_tracker.py) — CLI & database
- [data_fetcher.py](data_fetcher.py) — Live data sources
- [analysis_tools.py](analysis_tools.py) — Analytics
- [tests/test_data_fetcher.py](tests/test_data_fetcher.py) — Unit tests
- [README.md](README.md) — User guide

---

## Changelog

### 2026-05-24 (session 4)
- Graphical CLI: `cli_display.py`, `app` interactive mode, Rich tables/charts on all commands

### 2026-05-24 (session 3)
- Auto-add members: `sync-members` CLI, roster sync on `update`, `ensure_member_for_trade`
- CapitolExposed full roster fetch + party/chamber normalization

### 2026-05-24 (session 2)
- CapitolExposed live API (`capitolexposed`, `capitaltrades`, `house` sources)
- Rate limiter, member index cache, SSL via certifi
- `update --refresh`, `--pages`; 37 live Pelosi trades imported in test
- Added `tests/test_data_fetcher.py` (7 tests)

### 2026-05-24 (session 1)
- Full CLI: `stats`, `report`, `trades`, `export`, `search`, `update`
- Cache, normalization, dedup pipeline
- DB indexes
