"""
Graphical terminal UI for Congressional Stock Tracker (Rich + plotext).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from congress_stock_tracker import format_display_date

try:
    from rich import box
    from rich.align import Align
    from rich.columns import Columns
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm, IntPrompt, Prompt
    from rich.table import Table
    from rich.text import Text
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import plotext as plt

    PLOTEXT_AVAILABLE = True
except ImportError:
    PLOTEXT_AVAILABLE = False


console = Console() if RICH_AVAILABLE else None

TRADE_STYLES = {"buy": "bold green", "sell": "bold red", "hold": "bold yellow"}
PARTY_STYLES = {
    "democratic": "blue",
    "republican": "red",
    "independent": "magenta",
}


def require_rich() -> None:
    if not RICH_AVAILABLE:
        raise SystemExit(
            "Graphical UI requires 'rich'. Install: pip install rich plotext"
        )


class GraphicalDisplay:
    """Rich-based terminal graphics for tracker output."""

    def __init__(self):
        require_rich()
        self.console = Console()

    def banner(self) -> None:
        self.console.print()
        self.console.print(
            Panel(
                Align.center(
                    Text.from_markup(
                        "[bold cyan]Congressional Stock Trading Tracker[/]\n"
                        "[dim]CLI · Live PTR data · Terminal charts[/]"
                    )
                ),
                border_style="cyan",
                box=box.DOUBLE,
            )
        )

    def success(self, msg: str) -> None:
        self.console.print(f"[bold green]✓[/] {msg}")

    def warning(self, msg: str) -> None:
        self.console.print(f"[bold yellow]![/] {msg}")

    def error(self, msg: str) -> None:
        self.console.print(f"[bold red]✗[/] {msg}")

    def info_panel(self, title: str, lines: Dict[str, str]) -> None:
        body = "\n".join(f"[bold]{k}:[/] {v}" for k, v in lines.items())
        self.console.print(Panel(body, title=title, border_style="blue"))

    def stat_cards(self, cards: List[Tuple[str, str, str]]) -> None:
        """cards: [(label, value, color_style), ...]"""
        panels = []
        for label, value, style in cards:
            panels.append(
                Panel(
                    Align.center(Text(value, style=f"bold {style}")),
                    title=label,
                    width=18,
                    border_style=style.split()[0] if style else "white",
                )
            )
        self.console.print(Columns(panels, equal=True, expand=True))

    def trades_table(
        self,
        trades: List[Dict],
        title: str = "Trades",
        total: Optional[int] = None,
    ) -> None:
        table = Table(
            title=title,
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=False,
            expand=True,
        )
        table.add_column("Date", style="dim", width=18)
        table.add_column("Symbol", style="bold white", width=8)
        table.add_column("Company", width=24)
        table.add_column("Type", width=6)
        table.add_column("Amount", width=18)
        table.add_column("Member", width=22)

        for t in trades:
            ttype = (t.get("trade_type") or "").lower()
            style = TRADE_STYLES.get(ttype, "")
            table.add_row(
                format_display_date(t.get("trade_date", "")),
                t.get("symbol", ""),
                (t.get("company") or "")[:22],
                Text(ttype.upper(), style=style),
                t.get("amount_range", ""),
                t.get("member_name", ""),
            )

        self.console.print(table)
        if total is not None and total > len(trades):
            self.console.print(
                f"[dim]Showing {len(trades)} of {total} — use pagination for more[/]"
            )

    def members_table(self, rows: List[Dict], title: str = "Members") -> None:
        table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
        table.add_column("Name", width=28)
        table.add_column("Party", width=14)
        table.add_column("Chamber", width=8)
        table.add_column("State", width=6)
        table.add_column("ID", width=10)
        for r in rows:
            party = (r.get("party") or "")
            pstyle = PARTY_STYLES.get(party.lower(), "white")
            table.add_row(
                r.get("name", ""),
                Text(party, style=pstyle),
                r.get("chamber", ""),
                r.get("state", ""),
                r.get("member_id", ""),
            )
        self.console.print(table)

    def stats_table(self, stats: List[Dict], year: Optional[int] = None) -> None:
        title = f"Yearly stats — {year}" if year else "Yearly stats — all years"
        table = Table(title=title, box=box.ROUNDED, header_style="bold cyan", expand=True)
        table.add_column("Member", width=26)
        table.add_column("Party", width=12)
        table.add_column("Chamber", width=8)
        table.add_column("Buys", justify="right", style="green")
        table.add_column("Sells", justify="right", style="red")
        table.add_column("Holds", justify="right", style="yellow")
        table.add_column("Total", justify="right", style="bold")
        table.add_column("Stocks", justify="right")

        for s in stats:
            party = s.get("party") or "Unknown"
            pstyle = PARTY_STYLES.get(str(party).lower(), "white")
            table.add_row(
                s.get("member_name", ""),
                Text(str(party), style=pstyle),
                s.get("chamber", ""),
                str(s.get("total_buys", 0)),
                str(s.get("total_sells", 0)),
                str(s.get("total_holds", 0)),
                str(s.get("total_trades", 0)),
                str(s.get("unique_stocks", 0)),
            )
        self.console.print(table)

    def bar_chart(self, title: str, labels: List[str], values: List[int], color: str = "cyan") -> None:
        if not labels or not values:
            self.warning("No data for chart")
            return
        if PLOTEXT_AVAILABLE:
            try:
                plt.clear_figure()
                plt.theme("dark")
                plt.title(title)
                short = [lbl[:10] for lbl in labels]
                plt.bar(short, values)
                plt.show()
                return
            except Exception:
                pass
        max_v = max(values) or 1
        style = color if color in ("green", "red", "yellow", "cyan", "blue", "magenta") else "cyan"
        self.console.print(f"\n[bold]{title}[/]")
        for lbl, val in zip(labels, values):
            bar_len = int(40 * val / max_v)
            bar = "█" * bar_len
            self.console.print(f"  {lbl:<12} [{style}]{bar}[/] {val}")

    def member_dashboard(self, tracker, member_name: str) -> bool:
        """Full graphical member report. Returns False if member not found."""
        import sqlite3

        report = tracker.member_report_dict(member_name)
        if not report:
            self.error(f"Member not found: {member_name}")
            return False

        member = report["member"]
        trades = report["trades"]
        yearly = report["yearly_stats"]

        party = member.get("party", "Unknown")
        pstyle = PARTY_STYLES.get(str(party).lower(), "white")
        self.console.print()
        self.console.print(
            Panel(
                Align.center(
                    Text.from_markup(
                        f"[bold size=20]{member.get('name', member_name)}[/]\n"
                        f"[{pstyle}]{party}[/] · {member.get('chamber', '')} · "
                        f"{member.get('state', '')} · ID {member.get('member_id', '')}"
                    )
                ),
                border_style="cyan",
                box=box.DOUBLE,
            )
        )

        buys = sum(t.get("trade_type") == "buy" for t in trades)
        sells = sum(t.get("trade_type") == "sell" for t in trades)
        holds = sum(t.get("trade_type") == "hold" for t in trades)
        symbols = len({t.get("symbol") for t in trades})

        self.stat_cards(
            [
                ("Buys", str(buys), "green"),
                ("Sells", str(sells), "red"),
                ("Holds", str(holds), "yellow"),
                ("Trades", str(len(trades)), "cyan"),
                ("Stocks", str(symbols), "magenta"),
            ]
        )

        if buys or sells or holds:
            self.bar_chart(
                "Trade mix",
                ["Buy", "Sell", "Hold"],
                [buys, sells, holds],
                color="green",
            )

        sym_counts: Dict[str, int] = {}
        for t in trades:
            sym = t.get("symbol", "")
            if sym:
                sym_counts[sym] = sym_counts.get(sym, 0) + 1
        top = sorted(sym_counts.items(), key=lambda x: -x[1])[:8]
        if top:
            self.bar_chart(
                "Top symbols",
                [x[0] for x in top],
                [x[1] for x in top],
                color="blue",
            )

        if yearly:
            tree = Tree("[bold]Financial years[/]")
            for y in yearly:
                branch = tree.add(
                    f"[cyan]FY {y.get('financial_year')}[/] — "
                    f"{y.get('total_trades')} trades"
                )
                branch.add(f"Buys: [green]{y.get('total_buys')}[/]")
                branch.add(f"Sells: [red]{y.get('total_sells')}[/]")
                branch.add(f"Holds: [yellow]{y.get('total_holds')}[/]")
            self.console.print(tree)

        recent = trades[:25]
        if recent:
            self.trades_table(recent, title=f"Recent trades — {member_name}", total=len(trades))
        else:
            self.warning("No trades on file. Run: update --member \"Name\"")
        return True

    def analysis_dashboard(self, tools) -> None:
        """Party/chamber analysis with charts."""
        from analysis_tools import AnalysisTools

        self.console.print(Panel("[bold]Market analysis[/]", border_style="magenta"))

        top = tools.get_top_traders(limit=8)
        if top:
            self.bar_chart(
                "Top traders (by count)",
                [t["member_name"][:14] for t in top],
                [t["total_trades"] for t in top],
                color="cyan",
            )

        party = tools.get_trading_by_party()
        if party:
            self.bar_chart(
                "Trades by party",
                list(party.keys()),
                [v["total"] for v in party.values()],
                color="blue",
            )

        stocks = tools.get_most_traded_stocks(limit=8)
        if stocks:
            table = Table(title="Most traded symbols", box=box.SIMPLE)
            table.add_column("Symbol", style="bold")
            table.add_column("Company")
            table.add_column("Trades", justify="right")
            table.add_column("Buys", style="green", justify="right")
            table.add_column("Sells", style="red", justify="right")
            for s in stocks:
                table.add_row(
                    s["symbol"],
                    (s.get("company") or "")[:28],
                    str(s["transaction_count"]),
                    str(s.get("buys", 0)),
                    str(s.get("sells", 0)),
                )
            self.console.print(table)

    def progress_task(self, description: str):
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=self.console,
        )


def run_interactive_app(tracker) -> None:
    """Interactive menu-driven CLI app."""
    require_rich()
    from analysis_tools import AnalysisTools
    from data_fetcher import CongressDataFetcher

    ui = GraphicalDisplay()
    tools = AnalysisTools(tracker.db_path)
    fetcher = CongressDataFetcher()

    ui.banner()
    ui.info_panel(
        "Database",
        {
            "Members": str(tracker.count_members()),
            "Path": tracker.db_path,
        },
    )

    while True:
        ui.console.print()
        ui.console.print(
            "[bold cyan]Menu[/]  "
            "[dim]1[/] Member report  [dim]2[/] Search  [dim]3[/] Stats  "
            "[dim]4[/] Analysis  [dim]5[/] Update  [dim]6[/] Sync  "
            "[dim]7[/] Export  [dim]8[/] Members  [dim]9[/] AI prompt  [dim]q[/] Quit"
        )
        choice = Prompt.ask(
            "Choice",
            choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "q"],
            default="1",
            show_choices=False,
        )

        if choice == "q":
            ui.success("Goodbye!")
            break

        try:
            if choice == "1":
                name = Prompt.ask("Member name", default="Ro Khanna")
                ui.member_dashboard(tracker, name)

            elif choice == "2":
                query = Prompt.ask("Search (name, symbol, company)", default="")
                member = Prompt.ask("Member filter (optional)", default="")
                limit = IntPrompt.ask("Max rows", default=30)
                trades, total = tracker.search_trades(
                    query=query or None,
                    member=member or None,
                    limit=limit,
                )
                ui.trades_table(trades, title="Search results", total=total)

            elif choice == "3":
                year = Prompt.ask("Year (blank = all)", default="")
                year_int = int(year) if year.strip().isdigit() else None
                stats = tracker.get_stats_filtered(year=year_int, sort_by="total_trades")
                ui.stats_table(stats[:40], year=year_int)
                if len(stats) > 40:
                    ui.warning(f"Showing 40 of {len(stats)} members")

            elif choice == "4":
                ui.analysis_dashboard(tools)

            elif choice == "5":
                name = Prompt.ask("Member (blank = traders in DB)", default="")
                pages = IntPrompt.ask("API pages", default=3)
                fetcher.max_pages = pages
                members = [name] if name.strip() else None
                with ui.progress_task("Updating...") as progress:
                    task = progress.add_task("Fetching live data...", total=None)
                    summary = fetcher.update_database(
                        tracker,
                        sources=["capitolexposed"],
                        member_names=members,
                    )
                    progress.update(task, completed=True)
                ui.success(
                    f"Imported {summary['imported']} trades · "
                    f"+{summary.get('members_added', 0)} members"
                )

            elif choice == "6":
                traders = Confirm.ask("Traders only?", default=True)
                with ui.progress_task("Syncing roster...") as progress:
                    task = progress.add_task("CapitolExposed roster", total=None)
                    s = fetcher.sync_members_from_roster(
                        tracker, traders_only=traders
                    )
                    progress.update(task, completed=True)
                ui.success(f"Added {s['added']}, updated {s['updated']}")

            elif choice == "7":
                member = Prompt.ask("Member filter (optional)", default="")
                fmt = Prompt.ask("Format", choices=["csv", "json"], default="csv")
                n = tracker.export_data(
                    filename="congress_trades_export",
                    fmt=fmt,
                    member=member or None,
                )
                ui.success(f"Exported {n} rows")

            elif choice == "8":
                rows = tracker.list_members(limit=20, traders_only=True)
                ui.members_table(rows, title="Members with trades")

            elif choice == "9":
                from ai_agent import CongressPromptAgent, execute_agent_plan

                agent = CongressPromptAgent(tracker)
                prompt = Prompt.ask("Ask the agent", default="show Nancy Pelosi buys in 2024")
                plan = agent.plan(prompt)
                ui.info_panel(
                    "Agent plan",
                    {
                        "Prompt": prompt,
                        "Action": plan.action,
                        "Command": plan.command,
                    },
                )

                if plan.action == "help":
                    ui.info_panel(
                        "Try prompts",
                        {str(i + 1): example for i, example in enumerate(agent.prompt_examples())},
                    )
                    continue

                if plan.action == "report":
                    member = plan.args.get("member")
                    if member:
                        ui.member_dashboard(tracker, member)
                    else:
                        ui.warning("Please include a member name, for example: report for Nancy Pelosi")
                    continue

                if plan.action == "analysis":
                    ui.analysis_dashboard(tools)
                    continue

                if plan.action in {"update", "sync"}:
                    with ui.progress_task(f"{plan.action.title()}...") as progress:
                        task = progress.add_task(plan.summary, total=None)
                        kind, result = execute_agent_plan(plan, tracker, fetcher=fetcher)
                        progress.update(task, completed=True)
                    if kind == "update":
                        ui.success(
                            f"Fetched {result['fetched']} · imported {result['imported']} · "
                            f"skipped {result['skipped']} · errors {result['errors']}"
                        )
                    else:
                        ui.success(f"Added {result['added']}, updated {result['updated']}")
                    continue

                kind, result = execute_agent_plan(plan, tracker, fetcher=fetcher)
                if kind == "stats":
                    ui.stats_table(result[:40], year=plan.args.get("year"))
                elif kind in {"trades", "search"}:
                    rows, total = result
                    ui.trades_table(rows, title=plan.summary, total=total)
                elif kind == "export":
                    ui.success(f"Exported {result} rows")

        except KeyboardInterrupt:
            ui.console.print()
            continue
        except Exception as e:
            ui.error(str(e))
