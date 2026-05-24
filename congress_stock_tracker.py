#!/usr/bin/env python3
"""
Congressional Stock Trader Tracking Agent
Tracks US Congress members' stock transactions from public APIs and sources
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import csv
import argparse

logger = logging.getLogger(__name__)

DISPLAY_DATE_FORMAT = "D Month YYYY"


def format_display_date(value: str) -> str:
    """Format an ISO date as DAY MONTH NAME YEAR for user-facing output."""
    if not value:
        return ""
    value = str(value).strip()
    try:
        dt = datetime.strptime(value[:10], "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%B')} {dt.year}"
    except ValueError:
        return value


def parse_user_date(value: Optional[str]) -> Optional[str]:
    """Parse supported user date inputs into ISO format for database queries."""
    if not value:
        return value
    value = str(value).strip()
    normalized = value.replace(",", "")
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(normalized, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def with_display_dates(row: Dict) -> Dict:
    """Return a copy of a trade row with user-facing date values."""
    formatted = dict(row)
    for key in ("trade_date", "filing_date"):
        if key in formatted:
            formatted[key] = format_display_date(formatted.get(key, ""))
    return formatted


class TradeType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class CongressMember:
    name: str
    party: str
    chamber: str  # House or Senate
    state: str
    member_id: str

@dataclass
class StockTrade:
    member_id: str
    member_name: str
    symbol: str
    company: str
    trade_date: str
    trade_type: str  # buy, sell, hold
    amount_range: str
    financial_year: int
    source: str
    filing_date: str

class CongressStockTracker:
    """Main agent for tracking congressional stock trades"""
    
    def __init__(self, db_path: str = "congress_stocks.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Members table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                member_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                party TEXT,
                chamber TEXT NOT NULL,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Stock trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT NOT NULL,
                member_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                company TEXT,
                trade_date TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                amount_range TEXT,
                financial_year INTEGER NOT NULL,
                source TEXT,
                filing_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(member_id) REFERENCES members(member_id),
                UNIQUE(member_id, symbol, trade_date, trade_type)
            )
        ''')
        
        # Aggregated stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yearly_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT NOT NULL,
                member_name TEXT NOT NULL,
                financial_year INTEGER NOT NULL,
                total_buys INTEGER DEFAULT 0,
                total_sells INTEGER DEFAULT 0,
                total_holds INTEGER DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                unique_stocks INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(member_id) REFERENCES members(member_id),
                UNIQUE(member_id, financial_year)
            )
        ''')
        
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trades_member_year ON trades(member_id, financial_year)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_type ON trades(trade_type)")

        conn.commit()
        conn.close()
    
    def add_member(self, member: CongressMember) -> bool:
        """Add or update a congress member in the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO members 
                (member_id, name, party, chamber, state)
                VALUES (?, ?, ?, ?, ?)
            ''', (member.member_id, member.name, member.party, member.chamber, member.state))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error("Error adding member: %s", e)
            return False

    def count_members(self) -> int:
        """Return total members in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM members")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def list_members(self, limit: int = 20, traders_only: bool = False) -> List[Dict]:
        """List members, optionally only those with trades."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if traders_only:
            cursor.execute(
                """
                SELECT m.*, COUNT(t.id) AS trade_count
                FROM members m
                INNER JOIN trades t ON m.member_id = t.member_id
                GROUP BY m.member_id
                ORDER BY trade_count DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            cursor.execute(
                "SELECT *, 0 AS trade_count FROM members ORDER BY name LIMIT ?",
                (limit,),
            )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def add_trade(self, trade: StockTrade) -> bool:
        """Add a stock trade record"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO trades 
                (member_id, member_name, symbol, company, trade_date, 
                 trade_type, amount_range, financial_year, source, filing_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (trade.member_id, trade.member_name, trade.symbol, trade.company,
                  trade.trade_date, trade.trade_type, trade.amount_range,
                  trade.financial_year, trade.source, trade.filing_date))
            inserted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return inserted
        except sqlite3.Error as e:
            print(f"Error adding trade: {e}")
            return False
    
    def import_sample_data(self):
        """Import sample congressional stock trading data for demonstration"""
        sample_members = [
            CongressMember("Nancy Pelosi", "Democratic", "House", "CA", "P000197"),
            CongressMember("Kevin McCarthy", "Republican", "House", "CA", "M000673"),
            CongressMember("Chuck Schumer", "Democratic", "Senate", "NY", "S000148"),
            CongressMember("Mitch McConnell", "Republican", "Senate", "KY", "M000355"),
            CongressMember("Alexandria Ocasio-Cortez", "Democratic", "House", "NY", "O000172"),
        ]
        
        for member in sample_members:
            self.add_member(member)
        
        # Sample trades for demonstration
        sample_trades = [
            StockTrade("P000197", "Nancy Pelosi", "MSFT", "Microsoft", "2024-03-15", "buy", "$250K-$500K", 2024, "sec.gov", "2024-03-20"),
            StockTrade("P000197", "Nancy Pelosi", "AAPL", "Apple", "2024-06-10", "buy", "$100K-$250K", 2024, "opensecrets.org", "2024-06-15"),
            StockTrade("P000197", "Nancy Pelosi", "MSFT", "Microsoft", "2024-09-20", "sell", "$500K-$1M", 2024, "sec.gov", "2024-09-25"),
            
            StockTrade("M000673", "Kevin McCarthy", "TSLA", "Tesla", "2024-02-01", "buy", "$100K-$250K", 2024, "capitoltrades.com", "2024-02-05"),
            StockTrade("M000673", "Kevin McCarthy", "NVDA", "Nvidia", "2024-05-15", "buy", "$50K-$100K", 2024, "opensecrets.org", "2024-05-20"),
            StockTrade("M000673", "Kevin McCarthy", "TSLA", "Tesla", "2024-08-10", "sell", "$100K-$250K", 2024, "sec.gov", "2024-08-15"),
            
            StockTrade("S000148", "Chuck Schumer", "JPM", "JPMorgan", "2024-01-10", "hold", "$250K-$500K", 2024, "sec.gov", "2024-01-15"),
            StockTrade("S000148", "Chuck Schumer", "GOOGL", "Google", "2024-04-05", "buy", "$100K-$250K", 2024, "opensecrets.org", "2024-04-10"),
            
            StockTrade("M000355", "Mitch McConnell", "KO", "Coca Cola", "2024-03-20", "hold", "$50K-$100K", 2024, "sec.gov", "2024-03-25"),
            StockTrade("M000355", "Mitch McConnell", "XOM", "ExxonMobil", "2024-07-01", "buy", "$250K-$500K", 2024, "capitoltrades.com", "2024-07-05"),
            
            StockTrade("O000172", "Alexandria Ocasio-Cortez", "SPY", "SPY ETF", "2024-02-15", "hold", "$1K-$10K", 2024, "sec.gov", "2024-02-20"),
            StockTrade("O000172", "Alexandria Ocasio-Cortez", "VOO", "VOO ETF", "2024-05-10", "buy", "$5K-$25K", 2024, "opensecrets.org", "2024-05-15"),
        ]
        
        for trade in sample_trades:
            self.add_trade(trade)
        
        self.update_yearly_stats()
        print(f"✓ Imported {len(sample_members)} members and {len(sample_trades)} trades")
    
    def update_yearly_stats(self):
        """Calculate and update yearly statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get unique combinations of member_id and financial_year
        cursor.execute('''
            SELECT DISTINCT member_id, financial_year FROM trades
        ''')
        combos = cursor.fetchall()
        
        for member_id, year in combos:
            cursor.execute('''
                SELECT COUNT(*) FROM trades WHERE member_id = ? AND financial_year = ? AND trade_type = ?
            ''', (member_id, year, 'buy'))
            buys = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM trades WHERE member_id = ? AND financial_year = ? AND trade_type = ?
            ''', (member_id, year, 'sell'))
            sells = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM trades WHERE member_id = ? AND financial_year = ? AND trade_type = ?
            ''', (member_id, year, 'hold'))
            holds = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(DISTINCT symbol) FROM trades WHERE member_id = ? AND financial_year = ?
            ''', (member_id, year))
            unique_stocks = cursor.fetchone()[0]
            
            total_trades = buys + sells + holds
            
            cursor.execute('''
                SELECT member_name FROM trades WHERE member_id = ? LIMIT 1
            ''', (member_id,))
            member_name = cursor.fetchone()[0]
            
            cursor.execute('''
                INSERT OR REPLACE INTO yearly_stats
                (member_id, member_name, financial_year, total_buys, total_sells, total_holds, total_trades, unique_stocks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (member_id, member_name, year, buys, sells, holds, total_trades, unique_stocks))
        
        conn.commit()
        conn.close()
    
    def get_member_trades_by_year(self, member_name: str, year: int) -> List[Dict]:
        """Get all trades for a member in a specific financial year"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE member_name = ? AND financial_year = ?
            ORDER BY trade_date DESC
        ''', (member_name, year))
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades
    
    def get_yearly_summary(self, year: int = None) -> List[Dict]:
        """Get yearly summary for all members or a specific year"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if year:
            cursor.execute('''
                SELECT * FROM yearly_stats 
                WHERE financial_year = ?
                ORDER BY member_name
            ''', (year,))
        else:
            cursor.execute('''
                SELECT * FROM yearly_stats 
                ORDER BY financial_year DESC, member_name
            ''')
        
        stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return stats
    
    def get_trades_by_type(self, member_name: str, trade_type: str, year: int = None) -> List[Dict]:
        """Get trades of a specific type (buy/sell/hold) for a member"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if year:
            cursor.execute('''
                SELECT * FROM trades 
                WHERE member_name = ? AND trade_type = ? AND financial_year = ?
                ORDER BY trade_date DESC
            ''', (member_name, trade_type, year))
        else:
            cursor.execute('''
                SELECT * FROM trades 
                WHERE member_name = ? AND trade_type = ?
                ORDER BY financial_year DESC, trade_date DESC
            ''', (member_name, trade_type))
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades

    def query_trades(
        self,
        member: Optional[str] = None,
        trade_type: Optional[str] = None,
        year: Optional[int] = None,
        stock: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        query: Optional[str] = None,
        sort_by: str = "trade_date",
        sort_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict], int]:
        """Query trades with filters, sorting, and pagination. Returns (rows, total_count)."""
        allowed_sort = {
            "trade_date": "trade_date",
            "amount": "amount_range",
            "member": "member_name",
            "symbol": "symbol",
        }
        order_col = allowed_sort.get(sort_by, "trade_date")
        direction = "DESC" if sort_desc else "ASC"

        conditions = ["1=1"]
        params: List = []

        if member:
            conditions.append("member_name LIKE ?")
            params.append(f"%{member}%")
        if trade_type:
            conditions.append("trade_type = ?")
            params.append(trade_type.lower())
        if year:
            conditions.append("financial_year = ?")
            params.append(year)
        if stock:
            conditions.append("UPPER(symbol) = ?")
            params.append(stock.upper())
        if date_from:
            conditions.append("trade_date >= ?")
            params.append(parse_user_date(date_from))
        if date_to:
            conditions.append("trade_date <= ?")
            params.append(parse_user_date(date_to))
        if query:
            conditions.append("(member_name LIKE ? OR company LIKE ? OR symbol LIKE ?)")
            q = f"%{query}%"
            params.extend([q, q, q])

        where = " AND ".join(conditions)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM trades WHERE {where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT * FROM trades WHERE {where} ORDER BY {order_col} {direction} LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows, total

    def search_trades(
        self,
        query: Optional[str] = None,
        member: Optional[str] = None,
        stock: Optional[str] = None,
        trade_type: Optional[str] = None,
        year: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        amount_min: Optional[str] = None,
        amount_max: Optional[str] = None,
        sort_by: str = "trade_date",
        sort_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict], int]:
        """Full-text style search across trades."""
        rows, total = self.query_trades(
            member=member,
            trade_type=trade_type,
            year=year,
            stock=stock,
            date_from=date_from,
            date_to=date_to,
            query=query,
            sort_by=sort_by,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )
        if amount_min or amount_max:
            filtered = []
            for row in rows:
                amt = row.get("amount_range", "")
                if amount_min and amount_min not in amt:
                    continue
                if amount_max and amount_max not in amt:
                    continue
                filtered.append(row)
            return filtered, len(filtered)
        return rows, total

    def get_stats_filtered(
        self,
        year: Optional[int] = None,
        party: Optional[str] = None,
        chamber: Optional[str] = None,
        sort_by: str = "member_name",
    ) -> List[Dict]:
        """Yearly stats joined with member metadata and optional filters."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = ["1=1"]
        params: List = []
        if year:
            conditions.append("ys.financial_year = ?")
            params.append(year)
        if party:
            conditions.append("m.party LIKE ?")
            params.append(f"%{party}%")
        if chamber:
            conditions.append("m.chamber LIKE ?")
            params.append(f"%{chamber}%")

        allowed_sort = {"member_name", "total_trades", "total_buys", "total_sells", "financial_year"}
        order_col = sort_by if sort_by in allowed_sort else "member_name"

        cursor.execute(
            f"""
            SELECT ys.*, m.party, m.chamber, m.state
            FROM yearly_stats ys
            JOIN members m ON ys.member_id = m.member_id
            WHERE {' AND '.join(conditions)}
            ORDER BY ys.financial_year DESC, ys.{order_col} DESC
            """,
            params,
        )
        stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return stats

    def member_report_dict(self, member_name: str) -> Optional[Dict]:
        """Return member report as a JSON-serializable dict."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members WHERE name = ?", (member_name,))
        member = cursor.fetchone()
        if not member:
            conn.close()
            return None

        member_row = dict(member)
        cursor.execute(
            "SELECT * FROM trades WHERE member_id = ? ORDER BY financial_year DESC, trade_date DESC",
            (member_row["member_id"],),
        )
        trades = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            "SELECT * FROM yearly_stats WHERE member_id = ? ORDER BY financial_year DESC",
            (member_row["member_id"],),
        )
        yearly = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"member": member_row, "yearly_stats": yearly, "trades": trades}

    @staticmethod
    def print_trades_table(trades: List[Dict], title: str = "Trades") -> None:
        """Print a formatted table of trades."""
        if not trades:
            print("No trades found.")
            return
        print(f"\n{title} ({len(trades)} shown)")
        print(f"{'Date':<18} {'Symbol':<8} {'Company':<22} {'Type':<6} {'Amount':<16} {'Member':<28}")
        print("-" * 106)
        for t in trades:
            print(
                f"{format_display_date(t.get('trade_date','')):<18} {t.get('symbol',''):<8} "
                f"{(t.get('company') or '')[:20]:<22} {t.get('trade_type','').upper():<6} "
                f"{(t.get('amount_range') or ''):<16} {t.get('member_name',''):<28}"
            )

    def export_data(
        self,
        filename: str = "congress_trades_export",
        fmt: str = "csv",
        fields: Optional[List[str]] = None,
        year: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        member: Optional[str] = None,
    ) -> int:
        """Export trades to CSV or JSON with optional filters."""
        default_fields = [
            "id", "member_id", "member_name", "symbol", "company",
            "trade_date", "trade_type", "amount_range", "financial_year",
            "source", "filing_date",
        ]
        export_fields = fields or default_fields

        trades, _ = self.query_trades(
            member=member,
            year=year,
            date_from=date_from,
            date_to=date_to,
            limit=100000,
            offset=0,
        )
        if not trades:
            print("No trades to export")
            return 0

        if fmt == "json":
            path = filename if filename.endswith(".json") else f"{filename}.json"
            payload = [{k: with_display_dates(t).get(k) for k in export_fields if k in t} for t in trades]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        else:
            path = filename if filename.endswith(".csv") else f"{filename}.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=export_fields, extrasaction="ignore")
                writer.writeheader()
                for t in trades:
                    display_trade = with_display_dates(t)
                    writer.writerow({k: display_trade.get(k, "") for k in export_fields})

        print(f"✓ Exported {len(trades)} trades to {path}")
        return len(trades)

    def export_to_csv(self, filename: str = "congress_trades_export.csv"):
        """Export all trades to CSV file"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades ORDER BY financial_year DESC, member_name')
        trades = [dict(row) for row in cursor.fetchall()]
        
        if not trades:
            print("No trades to export")
            conn.close()
            return
        
        columns = [description[0] for description in cursor.description]
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for trade in trades:
                display_trade = with_display_dates(trade)
                writer.writerow([display_trade.get(column, "") for column in columns])
        
        conn.close()
        print(f"✓ Exported {len(trades)} trades to {filename}")
    
    def print_member_report(self, member_name: str):
        """Print a comprehensive report for a member"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM members WHERE name = ?', (member_name,))
        member = cursor.fetchone()
        
        if not member:
            print(f"Member '{member_name}' not found")
            conn.close()
            return
        
        member_id, name, party, chamber, state, _ = member
        
        print(f"\n{'='*70}")
        print(f"  {name.upper()} - {party.upper()} - {chamber.upper()} ({state})")
        print(f"{'='*70}\n")
        
        # Get all years with trades
        cursor.execute('''
            SELECT DISTINCT financial_year FROM trades WHERE member_id = ? ORDER BY financial_year DESC
        ''', (member_id,))
        years = [row[0] for row in cursor.fetchall()]
        
        for year in years:
            print(f"\n📅 Financial Year {year}")
            print(f"{'-'*70}")
            
            # Get stats for this year
            cursor.execute('''
                SELECT * FROM yearly_stats WHERE member_id = ? AND financial_year = ?
            ''', (member_id, year))
            stats = cursor.fetchone()
            
            if stats:
                _, _, _, _, buys, sells, holds, total, unique, _ = stats
                print(f"  Total Transactions: {total} | Buys: {buys} | Sells: {sells} | Holds: {holds} | Unique Stocks: {unique}")
            
            # Get trades by type
            cursor.execute('''
                SELECT symbol, company, trade_type, amount_range, trade_date FROM trades 
                WHERE member_id = ? AND financial_year = ?
                ORDER BY trade_date DESC
            ''', (member_id, year))
            
            trades = cursor.fetchall()
            if trades:
                print(f"\n  Transactions:")
                for symbol, company, ttype, amount, date in trades:
                    emoji = "📈" if ttype == "buy" else ("📉" if ttype == "sell" else "📊")
                    print(
                        f"    {emoji} {format_display_date(date)} | "
                        f"{symbol:6} {company:20} | {ttype.upper():4} | {amount}"
                    )
        
        conn.close()
    
    def print_yearly_summary(
        self,
        year: int = None,
        party: str = None,
        chamber: str = None,
        sort_by: str = "member_name",
    ):
        """Print summary of all trades by year with optional party/chamber filters."""
        stats = self.get_stats_filtered(year=year, party=party, chamber=chamber, sort_by=sort_by)

        if not stats:
            print("No trading data found")
            return

        title = f"CONGRESSIONAL STOCK TRADING SUMMARY - {year}" if year else "CONGRESSIONAL STOCK TRADING SUMMARY - ALL YEARS"
        filters = []
        if party:
            filters.append(f"party={party}")
        if chamber:
            filters.append(f"chamber={chamber}")
        if filters:
            title += f" ({', '.join(filters)})"

        print(f"\n{'='*110}")
        print(f"  {title}")
        print(f"{'='*110}\n")

        by_year: Dict[int, List[Dict]] = {}
        for stat in stats:
            y = stat["financial_year"]
            by_year.setdefault(y, []).append(stat)

        for y in sorted(by_year.keys(), reverse=True):
            print(f"\n📅 Financial Year {y}")
            print(f"{'-'*110}")
            print(
                f"{'Member':<30} {'Party':<12} {'Chamber':<8} {'Buys':<6} "
                f"{'Sells':<6} {'Holds':<6} {'Total':<6} {'Stocks':<6}"
            )
            print(f"{'-'*110}")

            for stat in by_year[y]:
                print(
                    f"{stat['member_name']:<30} {(stat.get('party') or 'Unknown'):<12} "
                    f"{(stat.get('chamber') or ''):<8} {stat['total_buys']:<6} "
                    f"{stat['total_sells']:<6} {stat['total_holds']:<6} "
                    f"{stat['total_trades']:<6} {stat['unique_stocks']:<6}"
                )

            year_buys = sum(s["total_buys"] for s in by_year[y])
            year_sells = sum(s["total_sells"] for s in by_year[y])
            year_holds = sum(s["total_holds"] for s in by_year[y])
            year_total = sum(s["total_trades"] for s in by_year[y])
            print(f"{'-'*110}")
            print(
                f"{'YEAR TOTAL':<30} {'':<12} {'':<8} {year_buys:<6} "
                f"{year_sells:<6} {year_holds:<6} {year_total:<6}"
            )

def _use_graphical(args) -> bool:
    return not getattr(args, "plain", False)


def main():
    parser = argparse.ArgumentParser(
        description="Congressional Stock Trading Tracker",
        epilog="Tip: run 'app' for interactive graphical CLI",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain text output (no Rich charts/tables)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser(
        "app",
        help="Launch interactive graphical CLI (menus, charts, tables)",
    )

    init_parser = subparsers.add_parser("init", help="Initialize database with sample data")
    init_parser.add_argument("--force", action="store_true", help="Re-import sample data")

    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_parser.add_argument("--member", help="Member name")
    report_parser.add_argument("--year", type=int, help="Financial year")
    report_parser.add_argument("--all", action="store_true", help="Show all members summary")
    report_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    trades_parser = subparsers.add_parser("trades", help="Look up trades")
    trades_parser.add_argument("--member", help="Member name (partial match)")
    trades_parser.add_argument("--year", type=int, help="Financial year")
    trades_parser.add_argument("--type", choices=["buy", "sell", "hold"], help="Trade type")
    trades_parser.add_argument("--stock", help="Stock ticker symbol")
    trades_parser.add_argument("--sort-by", choices=["date", "amount", "member", "symbol"], default="date")
    trades_parser.add_argument("--asc", action="store_true", help="Sort ascending")
    trades_parser.add_argument("--limit", type=int, default=50, help="Max results (default 50)")
    trades_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")

    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--format", choices=["csv", "json"], default="csv", help="Export format")
    export_parser.add_argument("--output", default="congress_trades_export", help="Output filename (no extension)")
    export_parser.add_argument("--fields", help="Comma-separated field list")
    export_parser.add_argument("--year", type=int, help="Filter by financial year")
    export_parser.add_argument("--from", dest="date_from", help="Start date, e.g. '15 March 2024'")
    export_parser.add_argument("--to", dest="date_to", help="End date, e.g. '31 December 2024'")
    export_parser.add_argument("--member", help="Filter by member name")

    stats_parser = subparsers.add_parser("stats", help="Show yearly statistics")
    stats_parser.add_argument("--year", type=int, help="Specific year")
    stats_parser.add_argument("--party", help="Filter by party (partial match)")
    stats_parser.add_argument("--chamber", choices=["House", "Senate"], help="Filter by chamber")
    stats_parser.add_argument(
        "--sort-by",
        choices=["member_name", "total_trades", "total_buys", "total_sells"],
        default="member_name",
    )

    update_parser = subparsers.add_parser("update", help="Fetch latest data from sources")
    update_parser.add_argument(
        "--source",
        action="append",
        choices=["all", "opensecrets", "capitaltrades", "capitolexposed", "sec", "house", "senate"],
        help="Data source(s) to update (repeatable)",
    )
    update_parser.add_argument("--member", action="append", help="Limit update to member(s)")
    update_parser.add_argument("--refresh", action="store_true", help="Clear cache before fetching")
    update_parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Max API pages per source (default: CAPITOL_MAX_PAGES env or 5)",
    )
    update_parser.add_argument(
        "--no-sync-members",
        action="store_true",
        help="Skip auto-syncing member roster before update",
    )
    update_parser.add_argument(
        "--all-members",
        action="store_true",
        help="Sync full in-office roster (not just members with trades)",
    )

    sync_parser = subparsers.add_parser(
        "sync-members", help="Sync Congress member roster from CapitolExposed API"
    )
    sync_parser.add_argument(
        "--traders-only",
        action="store_true",
        help="Only add members who have at least one reported trade",
    )
    sync_parser.add_argument(
        "--include-former",
        action="store_true",
        help="Include members no longer in office",
    )
    sync_parser.add_argument("--refresh", action="store_true", help="Clear roster cache first")

    search_parser = subparsers.add_parser("search", help="Search trades")
    search_parser.add_argument("-q", "--query", help="Search member, company, or symbol")
    search_parser.add_argument("--member", help="Member name filter")
    search_parser.add_argument("--stock", help="Stock ticker")
    search_parser.add_argument("--type", choices=["buy", "sell", "hold"], dest="trade_type")
    search_parser.add_argument("--year", type=int)
    search_parser.add_argument("--from", dest="date_from", help="Start date, e.g. '15 March 2024'")
    search_parser.add_argument("--to", dest="date_to", help="End date, e.g. '31 December 2024'")
    search_parser.add_argument("--sort-by", choices=["date", "amount", "member", "symbol"], default="date")
    search_parser.add_argument("--asc", action="store_true")
    search_parser.add_argument("--limit", type=int, default=50)
    search_parser.add_argument("--offset", type=int, default=0)

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.command:
        try:
            from cli_display import run_interactive_app

            tracker = CongressStockTracker()
            run_interactive_app(tracker)
        except SystemExit:
            parser.print_help()
        return

    tracker = CongressStockTracker()

    if args.command == "app":
        from cli_display import run_interactive_app

        run_interactive_app(tracker)
        return

    if args.command == "init":
        try:
            if args.force:
                logger.info("Force re-import: loading sample data...")
            tracker.import_sample_data()
            tracker.print_yearly_summary()
        except Exception as e:
            logger.error("Init failed: %s", e)
            raise SystemExit(1) from e

    elif args.command == "report":
        if args.member:
            if args.format == "json":
                report = tracker.member_report_dict(args.member)
                if report:
                    report["trades"] = [with_display_dates(trade) for trade in report["trades"]]
                    print(json.dumps(report, indent=2, default=str))
                else:
                    print(f"Member '{args.member}' not found")
                    raise SystemExit(1)
            elif _use_graphical(args):
                from cli_display import GraphicalDisplay

                ui = GraphicalDisplay()
                if not ui.member_dashboard(tracker, args.member):
                    raise SystemExit(1)
            else:
                tracker.print_member_report(args.member)
        elif args.all:
            if _use_graphical(args):
                from cli_display import GraphicalDisplay

                ui = GraphicalDisplay()
                stats = tracker.get_stats_filtered(year=args.year, sort_by="total_trades")
                ui.stats_table(stats[:50], year=args.year)
            else:
                tracker.print_yearly_summary(year=args.year)
        else:
            print("Please specify --member or --all")
            raise SystemExit(1)

    elif args.command == "trades":
        sort_map = {"date": "trade_date", "amount": "amount", "member": "member", "symbol": "symbol"}
        trades, total = tracker.query_trades(
            member=args.member,
            trade_type=args.type,
            year=args.year,
            stock=args.stock,
            sort_by=sort_map.get(args.sort_by, "trade_date"),
            sort_desc=not args.asc,
            limit=args.limit,
            offset=args.offset,
        )
        title = "Trades"
        if args.member:
            title += f" for {args.member}"
        if _use_graphical(args):
            from cli_display import GraphicalDisplay

            GraphicalDisplay().trades_table(trades, title=title, total=total)
        else:
            tracker.print_trades_table(trades, title=title)
            if total > args.limit:
                print(f"\nShowing {len(trades)} of {total} (use --offset to paginate)")

    elif args.command == "export":
        fields = args.fields.split(",") if args.fields else None
        tracker.export_data(
            filename=args.output,
            fmt=args.format,
            fields=fields,
            year=args.year,
            date_from=args.date_from,
            date_to=args.date_to,
            member=args.member,
        )

    elif args.command == "stats":
        if _use_graphical(args):
            from cli_display import GraphicalDisplay

            stats = tracker.get_stats_filtered(
                year=args.year, party=args.party, chamber=args.chamber, sort_by=args.sort_by
            )
            GraphicalDisplay().stats_table(stats, year=args.year)
        else:
            tracker.print_yearly_summary(
                year=args.year, party=args.party, chamber=args.chamber, sort_by=args.sort_by
            )

    elif args.command == "update":
        from data_fetcher import CongressDataFetcher

        sources = args.source or ["capitolexposed"]
        if "all" in sources:
            sources = list(CongressDataFetcher.SOURCES)
        fetcher = CongressDataFetcher()
        if args.pages:
            fetcher.max_pages = args.pages
        if args.refresh:
            removed = fetcher.clear_cache()
            logger.info("Cleared %d cache file(s)", removed)
        if _use_graphical(args):
            from cli_display import GraphicalDisplay

            ui = GraphicalDisplay()
            ui.info_panel("Update", {"Sources": ", ".join(sources)})
            with ui.progress_task("Updating") as progress:
                task = progress.add_task("Fetching...", total=None)
                summary = fetcher.update_database(
                    tracker,
                    sources=sources,
                    member_names=args.member,
                    sync_members=not args.no_sync_members,
                    traders_only_sync=not args.all_members,
                    force_roster_refresh=args.refresh,
                )
                progress.update(task, completed=True)
            ui.success(
                f"Members +{summary.get('members_added', 0)} · "
                f"Trades imported {summary['imported']}/{summary['fetched']}"
            )
        else:
            print(f"Updating from source(s): {', '.join(sources)}...")
            summary = fetcher.update_database(
                tracker,
                sources=sources,
                member_names=args.member,
                sync_members=not args.no_sync_members,
                traders_only_sync=not args.all_members,
                force_roster_refresh=args.refresh,
            )
            print(
                f"✓ Update complete — members: +{summary.get('members_added', 0)} new, "
                f"{summary.get('members_updated', 0)} updated, "
                f"{summary.get('members_auto_added', 0)} auto-added from trades | "
                f"trades: fetched {summary['fetched']}, imported {summary['imported']}, "
                f"skipped {summary['skipped']}, errors {summary['errors']}"
            )

    elif args.command == "sync-members":
        from data_fetcher import CongressDataFetcher

        fetcher = CongressDataFetcher()
        if args.refresh:
            fetcher.clear_cache()
        before = tracker.count_members()
        summary = fetcher.sync_members_from_roster(
            tracker,
            traders_only=args.traders_only,
            in_office_only=not args.include_former,
            force_refresh=args.refresh,
        )
        after = tracker.count_members()
        print(
            f"✓ Member sync complete — roster: {summary['total_roster']}, "
            f"added: {summary['added']}, updated: {summary['updated']}, "
            f"skipped: {summary['skipped']} | DB members: {before} → {after}"
        )

    elif args.command == "search":
        sort_map = {"date": "trade_date", "amount": "amount", "member": "member", "symbol": "symbol"}
        trades, total = tracker.search_trades(
            query=args.query,
            member=args.member,
            stock=args.stock,
            trade_type=args.trade_type,
            year=args.year,
            date_from=args.date_from,
            date_to=args.date_to,
            sort_by=sort_map.get(args.sort_by, "trade_date"),
            sort_desc=not args.asc,
            limit=args.limit,
            offset=args.offset,
        )
        if _use_graphical(args):
            from cli_display import GraphicalDisplay

            GraphicalDisplay().trades_table(trades, title="Search results", total=total)
        else:
            tracker.print_trades_table(trades, title="Search results")
            if total > args.limit:
                print(f"\nShowing {len(trades)} of {total} (use --offset to paginate)")

if __name__ == '__main__':
    main()
