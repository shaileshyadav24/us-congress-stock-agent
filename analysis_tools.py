#!/usr/bin/env python3
"""
Utility functions for Congressional Stock Tracker
Advanced operations and analysis tools
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Tuple
from congress_stock_tracker import CongressStockTracker

class AnalysisTools:
    """Advanced analysis and reporting tools"""
    
    def __init__(self, db_path: str = "congress_stocks.db"):
        self.tracker = CongressStockTracker(db_path)
        self.db_path = db_path
    
    def get_top_traders(self, year: int = None, limit: int = 10) -> List[Dict]:
        """Get members with most trading activity"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if year:
            cursor.execute('''
                SELECT member_name, total_trades, total_buys, total_sells, total_holds
                FROM yearly_stats
                WHERE financial_year = ?
                ORDER BY total_trades DESC
                LIMIT ?
            ''', (year, limit))
        else:
            cursor.execute('''
                SELECT member_name, total_trades, total_buys, total_sells, total_holds
                FROM yearly_stats
                ORDER BY total_trades DESC
                LIMIT ?
            ''', (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_most_traded_stocks(self, year: int = None, limit: int = 10) -> List[Dict]:
        """Get most traded stocks by Congress members"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if year:
            cursor.execute('''
                SELECT symbol, company, COUNT(*) as transaction_count,
                       SUM(CASE WHEN trade_type = 'buy' THEN 1 ELSE 0 END) as buys,
                       SUM(CASE WHEN trade_type = 'sell' THEN 1 ELSE 0 END) as sells
                FROM trades
                WHERE financial_year = ?
                GROUP BY symbol
                ORDER BY transaction_count DESC
                LIMIT ?
            ''', (year, limit))
        else:
            cursor.execute('''
                SELECT symbol, company, COUNT(*) as transaction_count,
                       SUM(CASE WHEN trade_type = 'buy' THEN 1 ELSE 0 END) as buys,
                       SUM(CASE WHEN trade_type = 'sell' THEN 1 ELSE 0 END) as sells
                FROM trades
                GROUP BY symbol
                ORDER BY transaction_count DESC
                LIMIT ?
            ''', (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_trading_by_party(self, year: int = None) -> Dict[str, Dict]:
        """Analyze trading patterns by political party"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if year:
            cursor.execute('''
                SELECT m.party, 
                       COUNT(CASE WHEN t.trade_type = 'buy' THEN 1 END) as buys,
                       COUNT(CASE WHEN t.trade_type = 'sell' THEN 1 END) as sells,
                       COUNT(CASE WHEN t.trade_type = 'hold' THEN 1 END) as holds,
                       COUNT(*) as total
                FROM trades t
                JOIN members m ON t.member_id = m.member_id
                WHERE t.financial_year = ?
                GROUP BY m.party
            ''', (year,))
        else:
            cursor.execute('''
                SELECT m.party, 
                       COUNT(CASE WHEN t.trade_type = 'buy' THEN 1 END) as buys,
                       COUNT(CASE WHEN t.trade_type = 'sell' THEN 1 END) as sells,
                       COUNT(CASE WHEN t.trade_type = 'hold' THEN 1 END) as holds,
                       COUNT(*) as total
                FROM trades t
                JOIN members m ON t.member_id = m.member_id
                GROUP BY m.party
            ''')
        
        results = cursor.fetchall()
        conn.close()
        
        analysis = {}
        for party, buys, sells, holds, total in results:
            analysis[party] = {
                'buys': buys,
                'sells': sells,
                'holds': holds,
                'total': total,
                'buy_ratio': round(buys / total * 100, 1) if total > 0 else 0
            }
        
        return analysis
    
    def get_trading_by_chamber(self, year: int = None) -> Dict[str, Dict]:
        """Analyze trading patterns by chamber (House vs Senate)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if year:
            cursor.execute('''
                SELECT m.chamber, 
                       COUNT(CASE WHEN t.trade_type = 'buy' THEN 1 END) as buys,
                       COUNT(CASE WHEN t.trade_type = 'sell' THEN 1 END) as sells,
                       COUNT(CASE WHEN t.trade_type = 'hold' THEN 1 END) as holds,
                       COUNT(*) as total
                FROM trades t
                JOIN members m ON t.member_id = m.member_id
                WHERE t.financial_year = ?
                GROUP BY m.chamber
            ''', (year,))
        else:
            cursor.execute('''
                SELECT m.chamber, 
                       COUNT(CASE WHEN t.trade_type = 'buy' THEN 1 END) as buys,
                       COUNT(CASE WHEN t.trade_type = 'sell' THEN 1 END) as sells,
                       COUNT(CASE WHEN t.trade_type = 'hold' THEN 1 END) as holds,
                       COUNT(*) as total
                FROM trades t
                JOIN members m ON t.member_id = m.member_id
                GROUP BY m.chamber
            ''')
        
        results = cursor.fetchall()
        conn.close()
        
        analysis = {}
        for chamber, buys, sells, holds, total in results:
            analysis[chamber] = {
                'buys': buys,
                'sells': sells,
                'holds': holds,
                'total': total,
                'buy_ratio': round(buys / total * 100, 1) if total > 0 else 0
            }
        
        return analysis
    
    def get_member_sector_analysis(self, member_name: str) -> Dict[str, int]:
        """Get stock sectors traded by a member"""
        sectors = {
            'Technology': ['MSFT', 'AAPL', 'GOOGL', 'NVDA', 'META', 'TSLA'],
            'Finance': ['JPM', 'GS', 'BAC', 'WFC', 'SCHW'],
            'Energy': ['XOM', 'CVX', 'COP', 'MPC'],
            'Healthcare': ['JNJ', 'PFE', 'UNH', 'ABBV'],
            'Consumer': ['KO', 'MCD', 'PG', 'WMT'],
            'Industrials': ['BA', 'CAT', 'GE'],
            'ETF': ['SPY', 'VOO', 'VTI', 'QQQ']
        }
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT symbol FROM trades WHERE member_name = ?', (member_name,))
        member_stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        sector_count = {}
        for sector, symbols in sectors.items():
            count = sum(1 for stock in member_stocks if stock in symbols)
            if count > 0:
                sector_count[sector] = count
        
        return sector_count
    
    def print_analysis_report(self):
        """Print comprehensive analysis report"""
        print("\n" + "="*80)
        print("  CONGRESSIONAL STOCK TRADING ANALYSIS REPORT")
        print("="*80)
        
        # Top traders
        print("\n📊 TOP TRADERS (by transaction count)")
        print("-"*80)
        top_traders = self.get_top_traders(limit=5)
        for i, trader in enumerate(top_traders, 1):
            print(f"{i}. {trader['member_name']:<30} {trader['total_trades']:>3} trades "
                  f"({trader['total_buys']} buy, {trader['total_sells']} sell, {trader['total_holds']} hold)")
        
        # Most traded stocks
        print("\n📈 MOST TRADED STOCKS")
        print("-"*80)
        top_stocks = self.get_most_traded_stocks(limit=5)
        for i, stock in enumerate(top_stocks, 1):
            print(f"{i}. {stock['symbol']:<6} {stock['company']:<30} {stock['transaction_count']:>2} trades "
                  f"({stock['buys']} buy, {stock['sells']} sell)")
        
        # Party analysis
        print("\n🏛️  TRADING BY PARTY")
        print("-"*80)
        party_analysis = self.get_trading_by_party()
        for party, stats in party_analysis.items():
            print(f"{party:<15} Buys: {stats['buys']:>2}  Sells: {stats['sells']:>2}  "
                  f"Holds: {stats['holds']:>2}  Total: {stats['total']:>2}  "
                  f"Buy Ratio: {stats['buy_ratio']:.1f}%")
        
        # Chamber analysis
        print("\n🏢 TRADING BY CHAMBER")
        print("-"*80)
        chamber_analysis = self.get_trading_by_chamber()
        for chamber, stats in chamber_analysis.items():
            print(f"{chamber:<15} Buys: {stats['buys']:>2}  Sells: {stats['sells']:>2}  "
                  f"Holds: {stats['holds']:>2}  Total: {stats['total']:>2}  "
                  f"Buy Ratio: {stats['buy_ratio']:.1f}%")

def main():
    """Run analysis report"""
    tools = AnalysisTools()
    tools.print_analysis_report()

if __name__ == '__main__':
    main()
