"""
Data Fetcher Module for Congressional Stock Trading Data
Sources: CapitolExposed (House PTR), OpenSecrets, SEC EDGAR (stubs)
"""

import hashlib
import json
import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VALID_TRADE_TYPES = {"buy", "sell", "hold"}
DEFAULT_CACHE_TTL = 3600
CAPITOL_EXPOSED_BASE = "https://www.capitolexposed.com/api/v1"
TX_TYPE_MAP = {"purchase": "buy", "sale": "sell", "exchange": "hold", "buy": "buy", "sell": "sell"}
PARTY_MAP = {
    "D": "Democratic",
    "R": "Republican",
    "I": "Independent",
    "DEM": "Democratic",
    "REP": "Republican",
    "IND": "Independent",
}


class RateLimiter:
    """Simple per-request throttle."""

    def __init__(self, min_interval: float = 0.3):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.time()


class CongressDataFetcher:
    """Fetches congressional trading data from public APIs"""

    SOURCES = ("opensecrets", "capitaltrades", "capitolexposed", "sec", "house", "senate")

    def __init__(self, cache_dir: str = ".cache", cache_ttl: int = DEFAULT_CACHE_TTL):
        self.cache_dir = Path(cache_dir)
        self.cache_ttl = cache_ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.opensecrets_api = "https://www.opensecrets.org/api"
        self.opensecrets_key = os.environ.get("OPENSECRETS_API_KEY", "")
        self.congress_api_key = os.environ.get("CONGRESS_API_KEY", "")
        self.max_pages = int(os.environ.get("CAPITOL_MAX_PAGES", "5"))
        self.rate_limiter = RateLimiter(min_interval=float(os.environ.get("FETCH_INTERVAL_SEC", "0.3")))
        self._members_index: Optional[Dict[str, Dict]] = None

    # ------------------------------------------------------------------ cache
    def _cache_key(self, source: str, identifier: str) -> Path:
        digest = hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()
        return self.cache_dir / f"{source}_{digest}.json"

    def _read_cache(self, path: Path) -> Optional[List[Dict]]:
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self.cache_ttl:
            logger.debug("Cache expired: %s", path)
            return None
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            logger.info("Cache hit: %s", path.name)
            return payload.get("trades", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Invalid cache file %s: %s", path, e)
            return None

    def _write_cache(self, path: Path, trades: List[Dict]) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"cached_at": datetime.now().astimezone().isoformat(), "trades": trades},
                    f,
                    indent=2,
                )
        except OSError as e:
            logger.warning("Failed to write cache %s: %s", path, e)

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        cafile = None
        try:
            import certifi

            cafile = certifi.where()
        except ImportError:
            bundled = Path(__file__).parent / "vendor" / "certifi" / "cacert.pem"
            if bundled.exists():
                cafile = str(bundled)
        if cafile:
            return ssl.create_default_context(cafile=cafile)
        return ssl.create_default_context()

    def _http_get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        self.rate_limiter.wait()
        req = urllib.request.Request(
            url,
            headers=headers
            or {
                "User-Agent": "CongressStockTracker/1.0 (research; github.com/congress-stock-tracker)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45, context=self._ssl_context()) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            logger.error("HTTP %s for %s", e.code, url)
        except urllib.error.URLError as e:
            logger.error("Network error for %s: %s", url, e.reason)
        except (json.JSONDecodeError, TimeoutError) as e:
            logger.error("Request failed for %s: %s", url, e)
        return None

    # ---------------------------------------------------- CapitolExposed API
    def fetch_capitolexposed_roster(self, force_refresh: bool = False) -> List[Dict]:
        """Fetch full member roster from CapitolExposed (deduped by bioguide_id)."""
        cache_path = self.cache_dir / "capitolexposed_roster_list.json"
        if not force_refresh and cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < self.cache_ttl:
                try:
                    with open(cache_path, encoding="utf-8") as f:
                        return json.load(f).get("members", [])
                except (json.JSONDecodeError, OSError):
                    pass

        by_bio: Dict[str, Dict] = {}
        page = 1
        while page <= 50:
            data = self._http_get_json(
                f"{CAPITOL_EXPOSED_BASE}/members?page={page}&per_page=20"
            )
            if not data or data.get("status") != "success":
                break
            for member in data.get("data", []):
                bio = member.get("bioguide_id")
                if bio:
                    by_bio[bio] = member
            meta = data.get("meta", {})
            if not meta.get("has_more"):
                break
            page += 1

        roster = list(by_bio.values())
        logger.info("CapitolExposed roster: %d members", len(roster))
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"cached_at": datetime.now().astimezone().isoformat(), "members": roster},
                    f,
                    indent=2,
                )
        except OSError:
            pass
        return roster

    def _build_members_index(self, roster: List[Dict]) -> Dict[str, Dict]:
        """Build lookup indexes from roster records."""
        index: Dict[str, Dict] = {}
        for member in roster:
            slug = member.get("slug", "")
            bio = member.get("bioguide_id", "")
            name = member.get("name", "")
            if slug:
                index[f"slug:{slug}"] = member
            if bio:
                index[f"bio:{bio}"] = member
            if name:
                index[f"name:{name.lower()}"] = member
        return index

    def _load_members_index(self, force_refresh: bool = False) -> Dict[str, Dict]:
        """Build lookup indexes: bioguide_id, slug, lowercase name -> member record."""
        if self._members_index is not None and not force_refresh:
            return self._members_index

        cache_path = self.cache_dir / "capitolexposed_members.json"
        if not force_refresh and cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < self.cache_ttl:
                try:
                    with open(cache_path, encoding="utf-8") as f:
                        self._members_index = json.load(f)
                        return self._members_index
                except (json.JSONDecodeError, OSError):
                    pass

        roster = self.fetch_capitolexposed_roster(force_refresh=force_refresh)
        index = self._build_members_index(roster)
        self._members_index = index
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(index, f)
        except OSError:
            pass
        return index

    @staticmethod
    def roster_record_to_member(record: Dict):
        """Convert CapitolExposed roster record to CongressMember."""
        from congress_stock_tracker import CongressMember

        bio = (record.get("bioguide_id") or "").strip()
        name = (record.get("name") or "").strip()
        if not bio or not name:
            return None

        party_code = str(record.get("party", "")).upper()
        party = PARTY_MAP.get(party_code, record.get("party") or "Unknown")
        chamber_raw = str(record.get("chamber", "house")).lower()
        chamber = "Senate" if chamber_raw == "senate" else "House"

        return CongressMember(
            name=name,
            party=party,
            chamber=chamber,
            state=(record.get("state") or "").strip(),
            member_id=bio,
        )

    def lookup_roster_record(
        self, member_id: str = "", member_name: str = ""
    ) -> Optional[Dict]:
        """Find roster record by bioguide ID or name."""
        index = self._load_members_index()
        if member_id:
            bio = member_id[2:] if member_id.startswith("m-") else member_id
            if f"bio:{bio}" in index:
                return index[f"bio:{bio}"]
        if member_name:
            key = f"name:{member_name.lower()}"
            if key in index:
                return index[key]
            last = member_name.split()[-1].lower()
            for k, record in index.items():
                if k.startswith("name:") and last in k[5:]:
                    return record
        return None

    def sync_members_from_roster(
        self,
        tracker,
        traders_only: bool = False,
        in_office_only: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, int]:
        """
        Add or update members in the database from the CapitolExposed roster.
        Returns counts: added, updated, skipped, total_roster.
        """
        roster = self.fetch_capitolexposed_roster(force_refresh=force_refresh)
        self._members_index = self._build_members_index(roster)

        conn = __import__("sqlite3").connect(tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT member_id FROM members")
        existing = {row[0] for row in cursor.fetchall()}
        conn.close()

        summary = {"added": 0, "updated": 0, "skipped": 0, "total_roster": len(roster)}

        for record in roster:
            if in_office_only and not record.get("in_office", True):
                summary["skipped"] += 1
                continue
            if traders_only and (record.get("trade_count") or 0) <= 0:
                summary["skipped"] += 1
                continue

            member = self.roster_record_to_member(record)
            if not member:
                summary["skipped"] += 1
                continue

            is_new = member.member_id not in existing
            tracker.add_member(member)
            if is_new:
                summary["added"] += 1
                existing.add(member.member_id)
            else:
                summary["updated"] += 1

        logger.info(
            "Member sync: %d added, %d updated, %d skipped (roster %d)",
            summary["added"],
            summary["updated"],
            summary["skipped"],
            summary["total_roster"],
        )
        return summary

    def ensure_member_for_trade(self, tracker, normalized: Dict) -> str:
        """
        Resolve member_id for a trade; auto-add from roster or trade metadata if missing.
        Returns bioguide member_id or empty string.
        """
        member_id = (normalized.get("member_id") or "").strip()
        if member_id.startswith("m-"):
            member_id = member_id[2:]
        member_name = (normalized.get("member_name") or "").strip()

        conn = __import__("sqlite3").connect(tracker.db_path)
        cursor = conn.cursor()
        if member_id:
            cursor.execute("SELECT member_id FROM members WHERE member_id = ?", (member_id,))
            if cursor.fetchone():
                conn.close()
                return member_id
        if member_name:
            cursor.execute("SELECT member_id FROM members WHERE name = ?", (member_name,))
            row = cursor.fetchone()
            if row:
                conn.close()
                return row[0]
        conn.close()

        record = self.lookup_roster_record(member_id=member_id, member_name=member_name)
        if record:
            member = self.roster_record_to_member(record)
            if member:
                tracker.add_member(member)
                return member.member_id

        if member_id and member_name:
            from congress_stock_tracker import CongressMember

            tracker.add_member(
                CongressMember(
                    name=member_name,
                    party="Unknown",
                    chamber="House",
                    state="",
                    member_id=member_id,
                )
            )
            logger.info("Auto-added member from trade metadata: %s (%s)", member_name, member_id)
            return member_id

        return ""

    @staticmethod
    def _name_to_slug(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug

    def resolve_member_slug(self, member_name: str, member_id: str = "") -> Optional[str]:
        """Resolve CapitolExposed member slug from name or bioguide ID."""
        index = self._load_members_index()
        if member_id and f"bio:{member_id}" in index:
            return index[f"bio:{member_id}"].get("slug")
        key = f"name:{member_name.lower()}"
        if key in index:
            return index[key].get("slug")
        # Partial name match
        name_lower = member_name.lower()
        for k, member in index.items():
            if k.startswith("name:") and name_lower in k[5:]:
                return member.get("slug")
        return self._name_to_slug(member_name)

    def _format_amount_range(self, amount_min: Optional[str], amount_max: Optional[str]) -> str:
        if not amount_min and not amount_max:
            return ""
        try:
            lo = int(amount_min) if amount_min else 0
            hi = int(amount_max) if amount_max else lo
            return f"${lo:,}-${hi:,}"
        except (ValueError, TypeError):
            return f"${amount_min}-${amount_max}" if amount_min else ""

    def _parse_capitolexposed_trade(self, item: Dict, member_name: str = "") -> Optional[Dict]:
        ticker = item.get("ticker") or ""
        if not ticker:
            return None
        tx_type = TX_TYPE_MAP.get(
            str(item.get("transaction_type", "hold")).lower(), "hold"
        )
        trade_date = (item.get("transaction_date") or "")[:10]
        filing_date = (item.get("disclosure_date") or "")[:10]
        raw_mid = item.get("member_id") or ""
        bio_id = raw_mid.replace("m-", "") if raw_mid else ""
        return {
            "member_name": member_name or item.get("member_name", ""),
            "member_id": bio_id,
            "symbol": ticker.upper().split(":")[0],
            "company": item.get("asset_description", ""),
            "trade_date": trade_date,
            "trade_type": tx_type,
            "amount_range": self._format_amount_range(
                item.get("amount_min"), item.get("amount_max")
            ),
            "source": "capitolexposed.com",
            "filing_date": filing_date,
        }

    def fetch_capitolexposed_trades(
        self,
        member_name: str = "",
        member_id: str = "",
        max_pages: Optional[int] = None,
    ) -> List[Dict]:
        """Fetch trades from CapitolExposed public API."""
        cache_id = member_name or member_id or "all"
        cache_path = self._cache_key("capitolexposed", cache_id)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        trades: List[Dict] = []
        pages_limit = max_pages or self.max_pages

        if member_name or member_id:
            slug = self.resolve_member_slug(member_name, member_id)
            if not slug:
                logger.warning("Could not resolve slug for %s", member_name or member_id)
                self._write_cache(cache_path, trades)
                return trades
            url_base = f"{CAPITOL_EXPOSED_BASE}/members/{slug}/trades"
        else:
            url_base = f"{CAPITOL_EXPOSED_BASE}/trades"

        page = 1
        while page <= pages_limit:
            sep = "&" if "?" in url_base else "?"
            data = self._http_get_json(f"{url_base}{sep}page={page}&per_page=100")
            if not data or data.get("status") != "success":
                break
            batch = data.get("data", [])
            if not batch:
                break
            for item in batch:
                parsed = self._parse_capitolexposed_trade(item, member_name)
                normalized = self.normalize_trade_data(parsed) if parsed else None
                if normalized:
                    trades.append(normalized)
            meta = data.get("meta", {})
            if not meta.get("has_more"):
                break
            page += 1

        logger.info(
            "CapitolExposed: fetched %d trades for %s",
            len(trades),
            member_name or member_id or "all",
        )
        self._write_cache(cache_path, trades)
        return trades

    # -------------------------------------------------------------- fetchers
    def fetch_opensecrets_trades(self, member_name: str) -> List[Dict]:
        """Fetch trading data from OpenSecrets.org API (requires OPENSECRETS_API_KEY)."""
        cache_path = self._cache_key("opensecrets", member_name)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        logger.info("Fetching from OpenSecrets: %s", member_name)
        trades: List[Dict] = []

        if not self.opensecrets_key:
            logger.warning(
                "OPENSECRETS_API_KEY not set — skipping live fetch. "
                "Set env var to enable OpenSecrets integration."
            )
            self._write_cache(cache_path, trades)
            return trades

        url = (
            f"{self.opensecrets_api}/?method=getLegislatorTrades"
            f"&apikey={self.opensecrets_key}&name={urllib.parse.quote(member_name)}"
            f"&output=json"
        )
        data = self._http_get_json(url)
        if data:
            raw = data.get("response", {}).get("trades", [])
            for item in raw:
                normalized = self.normalize_trade_data(
                    {
                        "member_name": member_name,
                        "symbol": item.get("ticker", ""),
                        "company": item.get("company", ""),
                        "trade_date": item.get("transaction_date", ""),
                        "trade_type": item.get("type", "hold"),
                        "amount_range": item.get("amount", ""),
                        "source": "opensecrets.org",
                        "filing_date": item.get("filing_date", ""),
                    }
                )
                if normalized:
                    trades.append(normalized)

        self._write_cache(cache_path, trades)
        return trades

    def fetch_capitaltrades_data(self, member_name: str, member_id: str = "") -> List[Dict]:
        """Fetch trades via CapitolExposed (aggregates House PTR data)."""
        return self.fetch_capitolexposed_trades(member_name=member_name, member_id=member_id)

    def fetch_sec_form4(self, member_id: str, years: int = 1) -> List[Dict]:
        """Fetch Form 4 filings from SEC EDGAR (stub — congressional PTR preferred)."""
        cache_path = self._cache_key("sec", f"{member_id}:{years}")
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        logger.info("SEC Form 4 fetch not yet implemented for %s", member_id)
        trades: List[Dict] = []
        self._write_cache(cache_path, trades)
        return trades

    def fetch_house_disclosures(self, max_pages: Optional[int] = None) -> List[Dict]:
        """Fetch recent House PTR trades via CapitolExposed bulk endpoint."""
        cache_path = self._cache_key("house", f"pages_{max_pages or self.max_pages}")
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        logger.info("Fetching House disclosures via CapitolExposed...")
        trades = self.fetch_capitolexposed_trades(max_pages=max_pages or self.max_pages)
        # Prefer records with House source URLs when present
        house_trades = [
            t
            for t in trades
            if "house.gov" in t.get("source", "") or t.get("source") == "capitolexposed.com"
        ]
        result = house_trades or trades
        self._write_cache(cache_path, result)
        return result

    def fetch_senate_disclosures(self) -> List[Dict]:
        """Fetch Senate financial disclosures (not yet available via CapitolExposed)."""
        cache_path = self._cache_key("senate", "all")
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        logger.info("Senate disclosure parser not yet implemented")
        trades: List[Dict] = []
        self._write_cache(cache_path, trades)
        return trades

    def fetch_congress_members(self, limit: int = 50) -> List[Dict]:
        """Fetch member roster from Congress.gov API (requires CONGRESS_API_KEY)."""
        if not self.congress_api_key:
            logger.debug("CONGRESS_API_KEY not set — skipping Congress.gov member fetch")
            return []

        url = (
            f"https://api.congress.gov/v3/member"
            f"?api_key={self.congress_api_key}&limit={limit}&format=json"
        )
        data = self._http_get_json(url)
        if not data:
            return []
        return data.get("members", [])

    def fetch_all_for_member(self, member_name: str, member_id: str = "") -> List[Dict]:
        """Aggregate trades from all configured sources for one member."""
        batches = [
            self.fetch_capitolexposed_trades(member_name=member_name, member_id=member_id),
            self.fetch_opensecrets_trades(member_name),
        ]
        if member_id:
            batches.append(self.fetch_sec_form4(member_id))
        return self.deduplicate_trades([t for batch in batches for t in batch])

    def fetch_by_source(
        self, source: str, member_name: str = "", member_id: str = ""
    ) -> List[Dict]:
        """Fetch from a single named source."""
        fetchers = {
            "opensecrets": lambda: self.fetch_opensecrets_trades(member_name),
            "capitaltrades": lambda: self.fetch_capitaltrades_data(member_name, member_id),
            "capitolexposed": lambda: self.fetch_capitolexposed_trades(
                member_name=member_name, member_id=member_id
            ),
            "sec": lambda: self.fetch_sec_form4(member_id or member_name),
            "house": self.fetch_house_disclosures,
            "senate": self.fetch_senate_disclosures,
        }
        if source not in fetchers:
            raise ValueError(f"Unknown source '{source}'. Choose from: {', '.join(self.SOURCES)}")
        return fetchers[source]()

    # --------------------------------------------------------- normalization
    def normalize_trade_data(self, trade_dict: Dict) -> Optional[Dict]:
        """Normalize trade data from different sources to a consistent format."""
        try:
            trade_date = self._normalize_date(trade_dict.get("trade_date", ""))
            filing_date = self._normalize_date(trade_dict.get("filing_date", ""))
            trade_type = str(trade_dict.get("trade_type", "hold")).lower().strip()
            trade_type = TX_TYPE_MAP.get(trade_type, trade_type)
            if trade_type not in VALID_TRADE_TYPES:
                trade_type = "hold"

            symbol = str(trade_dict.get("symbol", "")).upper().strip()
            if ":" in symbol:
                symbol = symbol.split(":")[0]
            financial_year = trade_dict.get("financial_year")
            if not financial_year and trade_date:
                financial_year = int(trade_date[:4])
            elif not financial_year:
                financial_year = datetime.now().year

            member_id = str(trade_dict.get("member_id", "")).strip()
            if member_id.startswith("m-"):
                member_id = member_id[2:]

            normalized = {
                "member_name": str(trade_dict.get("member_name", "")).strip(),
                "member_id": member_id,
                "symbol": symbol,
                "company": str(trade_dict.get("company", "")).strip(),
                "trade_date": trade_date,
                "trade_type": trade_type,
                "amount_range": str(trade_dict.get("amount_range", "")).strip(),
                "financial_year": int(financial_year),
                "source": str(trade_dict.get("source", "unknown")).strip(),
                "filing_date": filing_date,
            }
            if not self.validate_trade(normalized):
                return None
            return normalized
        except (ValueError, TypeError) as e:
            logger.error("Failed to normalize trade data: %s", e)
            return None

    def _normalize_date(self, value: str) -> str:
        """Standardize dates to YYYY-MM-DD."""
        if not value:
            return ""
        value = str(value).strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value[:10], fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        if len(value) >= 10 and value[4] == "-":
            return value[:10]
        return ""

    def validate_trade(self, trade: Dict) -> bool:
        """Validate normalized trade record."""
        if not trade.get("member_name") and not trade.get("member_id"):
            logger.debug("Rejected trade: missing member identifier")
            return False
        if not trade.get("symbol"):
            logger.debug("Rejected trade: missing symbol")
            return False
        if trade.get("trade_date"):
            try:
                dt = datetime.strptime(trade["trade_date"], "%Y-%m-%d")
                if dt.year < 2012 or dt > datetime.now() + timedelta(days=30):
                    logger.debug("Rejected trade: date out of range %s", trade["trade_date"])
                    return False
            except ValueError:
                logger.debug("Rejected trade: invalid date %s", trade["trade_date"])
                return False
        return True

    def deduplicate_trades(self, trades: List[Dict]) -> List[Dict]:
        """Remove duplicate trades (same member, symbol, date, type)."""
        seen = set()
        unique: List[Dict] = []
        for trade in trades:
            key = (
                trade.get("member_id") or trade.get("member_name", "").lower(),
                trade.get("symbol", ""),
                trade.get("trade_date", ""),
                trade.get("trade_type", ""),
            )
            if key not in seen:
                seen.add(key)
                unique.append(trade)
        return unique

    def clear_cache(self, source: Optional[str] = None) -> int:
        """Remove cache files. Returns count removed."""
        pattern = f"{source}_*" if source else "*.json"
        removed = 0
        for path in self.cache_dir.glob(pattern):
            path.unlink(missing_ok=True)
            removed += 1
        self._members_index = None
        roster_cache = self.cache_dir / "capitolexposed_roster_list.json"
        if roster_cache.exists() and (source is None or source == "capitolexposed"):
            roster_cache.unlink(missing_ok=True)
            removed += 1
        return removed

    @staticmethod
    def _uses_capitol_roster(sources: List[str]) -> bool:
        return bool(
            set(sources)
            & {"capitolexposed", "capitaltrades", "house", "all"}
        )

    # ----------------------------------------------------------- DB import
    def update_database(
        self,
        tracker,
        sources: Optional[List[str]] = None,
        member_names: Optional[List[str]] = None,
        sync_members: bool = True,
        traders_only_sync: bool = True,
        force_roster_refresh: bool = False,
    ) -> Dict[str, int]:
        """Fetch from sources and import into the tracker database."""
        from congress_stock_tracker import StockTrade

        sources = sources or list(self.SOURCES)
        summary = {
            "fetched": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "members_added": 0,
            "members_updated": 0,
            "members_auto_added": 0,
        }

        if sync_members and self._uses_capitol_roster(sources):
            ms = self.sync_members_from_roster(
                tracker,
                traders_only=traders_only_sync,
                in_office_only=True,
                force_refresh=force_roster_refresh,
            )
            summary["members_added"] = ms["added"]
            summary["members_updated"] = ms["updated"]

        conn = __import__("sqlite3").connect(tracker.db_path)
        cursor = conn.cursor()
        if member_names:
            placeholders = ",".join("?" * len(member_names))
            cursor.execute(
                f"SELECT member_id, name FROM members WHERE name IN ({placeholders})",
                member_names,
            )
        else:
            cursor.execute("SELECT member_id, name FROM members")
        members = cursor.fetchall()
        conn.close()

        all_trades: List[Dict] = []

        # Bulk sources (no per-member loop)
        if "house" in sources:
            all_trades.extend(self.fetch_house_disclosures())
        if "senate" in sources:
            all_trades.extend(self.fetch_senate_disclosures())

        per_member_sources = {
            s
            for s in sources
            if s in ("opensecrets", "capitaltrades", "capitolexposed", "sec")
        }
        if per_member_sources and members:
            for member_id, name in members:
                for source in per_member_sources:
                    try:
                        trades = self.fetch_by_source(source, name, member_id)
                        all_trades.extend(trades)
                    except Exception as e:
                        logger.error("Fetch %s failed for %s: %s", source, name, e)
                        summary["errors"] += 1

        all_trades = self.deduplicate_trades(all_trades)
        summary["fetched"] = len(all_trades)

        for raw in all_trades:
            normalized = self.normalize_trade_data(raw)
            if not normalized:
                summary["skipped"] += 1
                continue

            prior_count = tracker.count_members()
            member_id = self.ensure_member_for_trade(tracker, normalized)
            if tracker.count_members() > prior_count:
                summary["members_auto_added"] += 1

            if not member_id:
                summary["skipped"] += 1
                continue

            normalized["member_id"] = member_id
            trade = StockTrade(
                member_id=member_id,
                member_name=normalized["member_name"],
                symbol=normalized["symbol"],
                company=normalized["company"],
                trade_date=normalized["trade_date"] or datetime.now().strftime("%Y-%m-%d"),
                trade_type=normalized["trade_type"],
                amount_range=normalized["amount_range"],
                financial_year=normalized["financial_year"],
                source=normalized["source"],
                filing_date=normalized["filing_date"],
            )
            if tracker.add_trade(trade):
                summary["imported"] += 1
            else:
                summary["skipped"] += 1

        tracker.update_yearly_stats()
        return summary


def example_usage():
    """Example of how to use the data fetcher."""
    logging.basicConfig(level=logging.INFO)
    fetcher = CongressDataFetcher()
    print("\n=== Fetching Congressional Trading Data ===\n")
    pelosi = fetcher.fetch_capitolexposed_trades("Nancy Pelosi", "P000197", max_pages=1)
    print(f"CapitolExposed (Pelosi): {len(pelosi)} trades")
    house = fetcher.fetch_house_disclosures(max_pages=1)
    print(f"House bulk (1 page): {len(house)} trades")


if __name__ == "__main__":
    example_usage()
