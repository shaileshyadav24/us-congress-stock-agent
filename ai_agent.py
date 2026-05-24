"""Natural-language prompt agent for the congressional stock tracker."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class AgentPlan:
    """A parsed user request mapped to an existing app action."""

    action: str
    summary: str
    command: str
    args: Dict = field(default_factory=dict)


class CongressPromptAgent:
    """Rule-based agent that routes prompts to existing tracker commands."""

    def __init__(self, tracker, default_limit: int = 25):
        self.tracker = tracker
        self.default_limit = default_limit

    def plan(self, prompt: str) -> AgentPlan:
        text = " ".join(prompt.strip().split())
        lowered = text.lower()

        if not text:
            return AgentPlan(
                action="help",
                summary="Show examples of prompts I can handle.",
                command="ask --help",
            )

        year = self._extract_year(text)
        trade_type = self._extract_trade_type(lowered)
        stock = self._extract_stock(text)
        member = self._extract_member(text)
        limit = self._extract_limit(lowered) or self.default_limit

        if self._looks_like_help(lowered):
            return AgentPlan(
                action="help",
                summary="Show examples of prompts I can handle.",
                command="ask --help",
            )

        if any(word in lowered for word in ("sync", "roster", "members")) and "trade" not in lowered:
            return AgentPlan(
                action="sync",
                summary="Sync the congressional member roster.",
                command="sync-members --traders-only",
                args={"traders_only": True},
            )

        if any(word in lowered for word in ("fetch", "update", "refresh", "import", "pull")):
            sources = self._extract_sources(lowered)
            members = [member] if member else None
            return AgentPlan(
                action="update",
                summary=self._summary("Fetch live data", member=member, year=year, stock=stock),
                command=self._command_preview("update", sources=sources, member=member),
                args={
                    "sources": sources,
                    "members": members,
                    "pages": self._extract_pages(lowered),
                },
            )

        if any(word in lowered for word in ("export", "download", "save")):
            fmt = "json" if "json" in lowered else "csv"
            output = self._extract_output_name(text) or "congress_trades_export"
            return AgentPlan(
                action="export",
                summary=self._summary("Export trades", member=member, year=year, stock=stock),
                command=self._command_preview("export", fmt=fmt, output=output, member=member, year=year),
                args={"fmt": fmt, "output": output, "member": member, "year": year},
            )

        if any(word in lowered for word in ("analyze", "analysis", "top", "popular", "breakdown")):
            return AgentPlan(
                action="analysis",
                summary="Run the analysis dashboard.",
                command="python3 analysis_tools.py",
                args={"limit": limit},
            )

        if "stat" in lowered or "summary" in lowered or "yearly" in lowered:
            party = self._extract_party(lowered)
            chamber = self._extract_chamber(lowered)
            return AgentPlan(
                action="stats",
                summary=self._summary("Show trading statistics", year=year, party=party, chamber=chamber),
                command=self._command_preview("stats", year=year, party=party, chamber=chamber),
                args={"year": year, "party": party, "chamber": chamber},
            )

        if "report" in lowered or "dashboard" in lowered or "profile" in lowered:
            return AgentPlan(
                action="report",
                summary=self._summary("Show member report", member=member),
                command=self._command_preview("report", member=member),
                args={"member": member},
            )

        if member and not stock and any(word in lowered for word in ("show", "list", "find", "trade", "buy", "sell", "hold")):
            return AgentPlan(
                action="trades",
                summary=self._summary("Show member trades", member=member, year=year, trade_type=trade_type),
                command=self._command_preview(
                    "trades", member=member, year=year, trade_type=trade_type, limit=limit
                ),
                args={"member": member, "year": year, "trade_type": trade_type, "limit": limit},
            )

        query = stock or member or self._fallback_query(text)
        return AgentPlan(
            action="search",
            summary=self._summary(
                "Search trades",
                query=None if stock else query,
                stock=stock,
                member=member,
                year=year,
                trade_type=trade_type,
            ),
            command=self._command_preview(
                "search",
                query=None if stock else query,
                member=member,
                stock=stock,
                year=year,
                trade_type=trade_type,
                limit=limit,
            ),
            args={
                "query": None if stock else query,
                "member": member if stock else None,
                "stock": stock,
                "year": year,
                "trade_type": trade_type,
                "limit": limit,
            },
        )

    def prompt_examples(self) -> List[str]:
        return [
            "fetch latest trades for Ro Khanna",
            "show Nancy Pelosi buys in 2024",
            "search NVDA trades limit 10",
            "stats for 2024",
            "export Nancy Pelosi trades as json",
            "sync members",
            "show analysis",
        ]

    def _extract_member(self, text: str) -> Optional[str]:
        quoted = re.search(r'"([^"]+)"|\'([^\']+)\'', text)
        if quoted:
            return (quoted.group(1) or quoted.group(2)).strip()

        names = self._known_member_names()
        lowered = text.lower()
        for name in sorted(names, key=len, reverse=True):
            if name.lower() in lowered:
                return name
        last_name_matches = [
            name for name in names if name.split() and re.search(rf"\b{re.escape(name.split()[-1].lower())}\b", lowered)
        ]
        if len(last_name_matches) == 1:
            return last_name_matches[0]

        match = re.search(
            r"(?:for|member|by|from|of)\s+([A-Za-z.\-']+(?:\s+[A-Za-z.\-']+){0,3})",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            candidate = self._clean_member_candidate(match.group(1))
            if candidate:
                return candidate if any(ch.isupper() for ch in candidate) else candidate.title()
        return None

    def _known_member_names(self) -> List[str]:
        rows = self.tracker.list_members(limit=10000, traders_only=False)
        return [row.get("name", "") for row in rows if row.get("name")]

    @staticmethod
    def _clean_member_candidate(value: str) -> str:
        stop_words = {"trades", "trade", "buys", "sells", "holds", "stock", "stocks", "in", "from"}
        parts = []
        for part in value.split():
            if part.lower() in stop_words:
                break
            parts.append(part)
        return " ".join(parts).strip()

    @staticmethod
    def _extract_year(text: str) -> Optional[int]:
        match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_trade_type(lowered: str) -> Optional[str]:
        if re.search(r"\b(buy|buys|bought|purchase|purchases)\b", lowered):
            return "buy"
        if re.search(r"\b(sell|sells|sold|sale|sales)\b", lowered):
            return "sell"
        if re.search(r"\b(hold|holds|holding|holdings)\b", lowered):
            return "hold"
        return None

    @staticmethod
    def _extract_stock(text: str) -> Optional[str]:
        match = re.search(r"\b(?:ticker|symbol|stock)\s+([A-Z]{1,5})\b", text)
        if match:
            return match.group(1)
        tokens = re.findall(r"\b[A-Z]{2,5}\b", text)
        ignored = {"USA", "US", "SEC", "JSON", "CSV", "PTR", "API"}
        for token in tokens:
            if token not in ignored:
                return token
        return None

    @staticmethod
    def _extract_limit(lowered: str) -> Optional[int]:
        match = re.search(r"\b(?:limit|top|first|show)\s+(\d{1,4})\b", lowered)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_pages(lowered: str) -> Optional[int]:
        match = re.search(r"\b(?:page|pages)\s+(\d{1,3})\b", lowered)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_party(lowered: str) -> Optional[str]:
        if "democrat" in lowered:
            return "Democratic"
        if "republican" in lowered or "gop" in lowered:
            return "Republican"
        if "independent" in lowered:
            return "Independent"
        return None

    @staticmethod
    def _extract_chamber(lowered: str) -> Optional[str]:
        if "house" in lowered:
            return "House"
        if "senate" in lowered:
            return "Senate"
        return None

    @staticmethod
    def _extract_sources(lowered: str) -> List[str]:
        source_aliases = {
            "opensecrets": "opensecrets",
            "capitaltrades": "capitaltrades",
            "capitolexposed": "capitolexposed",
            "capitol exposed": "capitolexposed",
            "sec": "sec",
            "house": "house",
            "senate": "senate",
            "all": "all",
        }
        sources = [source for alias, source in source_aliases.items() if alias in lowered]
        if "all" in sources:
            return ["all"]
        return sources or ["capitolexposed"]

    @staticmethod
    def _extract_output_name(text: str) -> Optional[str]:
        match = re.search(r"\b(?:to|as|named)\s+([A-Za-z0-9_\-./]+)\b", text)
        if match:
            value = match.group(1)
            if value.lower() not in {"csv", "json"}:
                return value.rsplit(".", 1)[0]
        return None

    @staticmethod
    def _fallback_query(text: str) -> str:
        cleaned = re.sub(
            r"\b(show|list|find|search|trades?|stocks?|for|in|buy|sell|hold|buys|sells|holds)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        return " ".join(cleaned.split()).strip()

    @staticmethod
    def _looks_like_help(lowered: str) -> bool:
        return lowered in {"help", "?", "examples"} or "what can you" in lowered

    @staticmethod
    def _summary(base: str, **kwargs) -> str:
        parts = [base]
        for key, value in kwargs.items():
            if value:
                parts.append(f"{key.replace('_', ' ')}={value}")
        return " · ".join(parts)

    @staticmethod
    def _command_preview(command: str, **kwargs) -> str:
        pieces = [command]
        mapping = {
            "query": "-q",
            "member": "--member",
            "stock": "--stock",
            "year": "--year",
            "trade_type": "--type",
            "limit": "--limit",
            "party": "--party",
            "chamber": "--chamber",
            "fmt": "--format",
            "output": "--output",
        }
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "sources":
                for source in value:
                    pieces.extend(["--source", source])
                continue
            flag = mapping.get(key)
            if flag:
                pieces.extend([flag, f'"{value}"' if isinstance(value, str) and " " in value else str(value)])
        return " ".join(pieces)


def execute_agent_plan(plan: AgentPlan, tracker, fetcher=None) -> Tuple[str, object]:
    """Execute an agent plan using existing app command methods."""
    if plan.action == "help":
        return "help", None

    if plan.action == "stats":
        stats = tracker.get_stats_filtered(
            year=plan.args.get("year"),
            party=plan.args.get("party"),
            chamber=plan.args.get("chamber"),
            sort_by="total_trades",
        )
        return "stats", stats

    if plan.action == "report":
        member = plan.args.get("member")
        return "report", tracker.member_report_dict(member) if member else None

    if plan.action == "trades":
        rows, total = tracker.query_trades(
            member=plan.args.get("member"),
            trade_type=plan.args.get("trade_type"),
            year=plan.args.get("year"),
            limit=plan.args.get("limit", 25),
        )
        return "trades", (rows, total)

    if plan.action == "search":
        rows, total = tracker.search_trades(
            query=plan.args.get("query"),
            member=plan.args.get("member"),
            stock=plan.args.get("stock"),
            trade_type=plan.args.get("trade_type"),
            year=plan.args.get("year"),
            limit=plan.args.get("limit", 25),
        )
        return "search", (rows, total)

    if plan.action == "export":
        count = tracker.export_data(
            filename=plan.args.get("output") or "congress_trades_export",
            fmt=plan.args.get("fmt") or "csv",
            member=plan.args.get("member"),
            year=plan.args.get("year"),
        )
        return "export", count

    if plan.action == "analysis":
        from analysis_tools import AnalysisTools

        tools = AnalysisTools(tracker.db_path)
        return "analysis", {
            "top_traders": tools.get_top_traders(limit=plan.args.get("limit", 25)),
            "most_traded_stocks": tools.get_most_traded_stocks(limit=plan.args.get("limit", 25)),
            "party": tools.get_trading_by_party(),
            "chamber": tools.get_trading_by_chamber(),
        }

    if plan.action in {"update", "sync"}:
        if fetcher is None:
            from data_fetcher import CongressDataFetcher

            fetcher = CongressDataFetcher()

        if plan.action == "sync":
            return "sync", fetcher.sync_members_from_roster(
                tracker, traders_only=plan.args.get("traders_only", True)
            )

        if plan.args.get("pages"):
            fetcher.max_pages = plan.args["pages"]
        sources = plan.args.get("sources") or ["capitolexposed"]
        if "all" in sources:
            sources = list(fetcher.SOURCES)
        return "update", fetcher.update_database(
            tracker,
            sources=sources,
            member_names=plan.args.get("members"),
        )

    raise ValueError(f"Unsupported agent action: {plan.action}")
