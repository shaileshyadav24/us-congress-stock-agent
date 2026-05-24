# Congressional Stock Tracker - Quick Start Guide

## 🎯 What This Agent Does

This agent tracks and analyzes stock trading activities of US Congress members by:
1. **Collecting** trading data from public sources
2. **Organizing** transactions by member and financial year
3. **Categorizing** trades as buys, sells, or holdings
4. **Analyzing** patterns and generating reports

## 🚀 Get Started in 2 Minutes

### Step 1: Initialize the Database
```bash
python3 congress_stock_tracker.py init
```
This loads sample data for 5 Congress members with their 2024 trading activity.

### Step 2: View Statistics
```bash
python3 congress_stock_tracker.py stats
```
See an overview of all trading activity by member and year.

### Step 3: Get a Member Report
```bash
python3 congress_stock_tracker.py report --member "Nancy Pelosi"
```
View complete trading history and breakdown for a specific member.

## 📊 Common Tasks

### View All Trades for a Member
```bash
python3 congress_stock_tracker.py trades --member "Nancy Pelosi"
```

### See Only Buy Trades
```bash
python3 congress_stock_tracker.py trades --member "Nancy Pelosi" --type buy
```

### Export Data for Analysis
```bash
python3 congress_stock_tracker.py export
```
Creates `congress_trades_export.csv` with all trading data.

### Check Stats for a Specific Year
```bash
python3 congress_stock_tracker.py stats --year 2024
```

## 📈 Understanding the Output

### Yearly Statistics Table
```
Member                         Party        Buys  Sells  Holds  Total  Stocks  
Nancy Pelosi                   Democratic   2     1      0      3      2       
```

- **Buys**: Number of stock purchases
- **Sells**: Number of stock sales  
- **Holds**: Unchanged positions
- **Total**: Sum of all transactions
- **Stocks**: Number of unique stocks

### Member Report
Shows:
- Member name, party, chamber, state
- Year-by-year breakdown
- Transaction list with dates and amounts
- Icons: 📈 (buy), 📉 (sell), 📊 (hold)

## 🔗 Data Sources

The agent pulls from public sources:
- **OpenSecrets.org** - Political trading database
- **CapitalTrades.com** - Congressional trader tracker
- **SEC.gov** - Form 4 filings
- **House.gov** - Member disclosures
- **Senate.gov** - Ethics office filings

## 💾 Database Location

The agent creates a SQLite database: `congress_stocks.db`

To view the data directly:
```bash
sqlite3 congress_stocks.db
> SELECT * FROM trades;
> SELECT * FROM yearly_stats;
```

## 🔍 Advanced Usage

### Search Trades by Type and Year
```bash
python3 congress_stock_tracker.py trades --member "Kevin McCarthy" --type buy --year 2024
```

### View Sell Transactions Only
```bash
python3 congress_stock_tracker.py trades --member "Chuck Schumer" --type sell
```

## 📚 Sample Data Included

When you run `init`, the agent loads:

**Members (5 total):**
- Nancy Pelosi (House-CA, Democratic)
- Kevin McCarthy (House-CA, Republican)
- Chuck Schumer (Senate-NY, Democratic)
- Mitch McConnell (Senate-KY, Republican)
- Alexandria Ocasio-Cortez (House-NY, Democratic)

**Trades (12 total):**
- 7 buys, 2 sells, 3 holds
- Companies: Microsoft, Apple, Tesla, Nvidia, JPMorgan, Google, Coca Cola, ExxonMobil, ETFs
- Financial Year: 2024

## ❓ FAQ

**Q: Can I add my own data?**
A: Yes! The script provides methods to add members and trades programmatically.

**Q: Where does the data come from?**
A: All sources are public government disclosures and trading databases.

**Q: Can I search by stock symbol?**
A: Currently search by member. You can export to CSV and filter by symbol.

**Q: How often is data updated?**
A: With the data fetcher module, you can schedule regular updates.

**Q: Is this real-time data?**
A: The sample data is for demonstration. Real data sources have a 1-3 day reporting delay.

## 🛠️ Command Reference

```bash
# Initialize with sample data
python3 congress_stock_tracker.py init

# View yearly statistics
python3 congress_stock_tracker.py stats
python3 congress_stock_tracker.py stats --year 2024

# Get member report
python3 congress_stock_tracker.py report --member "NAME"
python3 congress_stock_tracker.py report --all

# Search trades
python3 congress_stock_tracker.py trades --member "NAME"
python3 congress_stock_tracker.py trades --member "NAME" --type buy
python3 congress_stock_tracker.py trades --member "NAME" --type sell --year 2024

# Export data
python3 congress_stock_tracker.py export
```

## 📂 Files in This Project

- `congress_stock_tracker.py` - Main agent (2,000+ lines)
- `data_fetcher.py` - Module for pulling real data from APIs
- `README.md` - Full documentation
- `QUICKSTART.md` - This file
- `congress_stocks.db` - SQLite database (created after init)
- `congress_trades_export.csv` - Exported data (created after export)

## 🎓 Learning Resources

1. **STOCK Act**: Congressional Stock Ownership Disclosure Act
2. **Form 4**: SEC disclosure of insider trading
3. **OpenSecrets**: https://www.opensecrets.org/
4. **CapitalTrades**: https://capitaltrades.com/
5. **House Ethics**: https://house.gov/administration/ethics

## Next Steps

1. Run `python3 congress_stock_tracker.py init`
2. Explore with `stats` and `report` commands
3. Export data: `python3 congress_stock_tracker.py export`
4. Analyze the CSV in Excel or Python

Enjoy tracking congressional trades! 📊
