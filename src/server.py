# src/server.py

import os
import datetime as dt
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# ✅ Use absolute imports so running as a module works
from src.kucoin_client import KucoinClient, KucoinBalance
from src.notion_client import NotionClient
from src.portfolio import aggregate_balances

load_dotenv()

mcp = FastMCP("mcp-crypto-portfolio")

# ---------- Models ----------
class HealthOut(BaseModel):
    ok: bool
    version: str

class GetBalancesOut(BaseModel):
    as_of: str
    balances: list[KucoinBalance]

class UpsertHoldingsIn(BaseModel):
    date_iso: str = Field(description="ISO date, e.g., 2025-09-25")
    note: str | None = None

class UpsertHoldingsOut(BaseModel):
    upserted: int

class ReportOut(BaseModel):
    as_of: str
    summary: str
    suggestions: list[str]
    notion_urls: list[str] = []

# ---------- Helpers ----------
def _need(name: str) -> str:
    """Fetch a required env var or raise a helpful error."""
    v = os.getenv(name)
    if not v:
        raise ValueError(f"Missing required environment variable: {name}")
    return v

def _kc() -> KucoinClient:
    """Build a KuCoin client from environment variables."""
    return KucoinClient(
        base_url=os.getenv("KUCOIN_BASE_URL", "https://api.kucoin.com"),
        api_key=_need("KUCOIN_API_KEY"),
        api_secret=_need("KUCOIN_API_SECRET"),
        api_passphrase=_need("KUCOIN_API_PASSPHRASE"),
        # If your KucoinClient supports key version, pass e.g. key_version=2 or 3 here.
    )

def _notion() -> NotionClient:
    return NotionClient(
        token=_need("NOTION_TOKEN"),
        database_id=_need("NOTION_DATABASE_ID"),
    )

# ---------- Tools ----------
@mcp.tool()
def health() -> HealthOut:
    """Basic health check for the MCP server."""
    return HealthOut(ok=True, version="0.4.0")

@mcp.tool()
def get_balances() -> GetBalancesOut:
    """
    Fetch KuCoin balances from both 'main' and 'trade' accounts.
    Requires KUCOIN_* env vars to be set inside the container.
    """
    kc = _kc()
    main = kc.get_accounts("main")
    trade = kc.get_accounts("trade")
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return GetBalancesOut(as_of=now, balances=main + trade)

@mcp.tool()
def upsert_holdings(args: UpsertHoldingsIn) -> UpsertHoldingsOut:
    """
    Aggregate balances and write one row per (asset, account, date) to Notion.
    """
    kc = _kc()
    n = _notion()

    main = kc.get_accounts("main")
    trade = kc.get_accounts("trade")

    upserted = 0
    for b in main + trade:
        page_id = n.query_asset_on_date(b.currency, args.date_iso, b.accountType)
        n.create_or_update_balance(
            asset=b.currency,
            date_iso=args.date_iso,
            account=b.accountType,
            amount=b.available,
            holds=b.holds,
            balance=b.balance,
            total_spent=None,  # cost basis ingestion can fill this later
            notes=args.note,
            page_id=page_id,
        )
        upserted += 1

    return UpsertHoldingsOut(upserted=upserted)

@mcp.tool()
def portfolio_report() -> ReportOut:
    """
    First-pass heuristic report (no USD prices yet):
    - Flags concentration
    - Notes dust
    - Checks stablecoin mix
    """
    kc = _kc()
    balances = kc.get_accounts("main") + kc.get_accounts("trade")
    positions = aggregate_balances(balances)

    total = sum(p.balance for p in positions) or 0.0
    suggestions: list[str] = []

    # Concentration (top-5)
    top = sorted(positions, key=lambda x: x.balance, reverse=True)[:5]
    for p in top:
        share = (p.balance / total * 100) if total else 0
        if share > 30:
            suggestions.append(f"{p.asset} is {share:.1f}% of portfolio — consider trimming.")

    # Dust
    for p in positions:
        if 0 < p.balance < 5:
            suggestions.append(f"{p.asset} balance is small ({p.balance:.4f}); consider consolidating.")

    # Stablecoin buffer
    stables = {"USDT", "USDC", "DAI", "FDUSD", "TUSD"}
    stable_sum = sum(p.balance for p in positions if p.asset in stables)
    if total:
        stable_share = stable_sum / total * 100
        if stable_share < 5:
            suggestions.append("Stablecoin buffer <5%; consider increasing dry powder.")
        elif stable_share > 40:
            suggestions.append("High stablecoin share (>40%); consider deploying if unintentional.")

    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    summary = f"{len(positions)} assets; unit-sum={total:.4f} (USD valuation added next)."
    return ReportOut(as_of=now, summary=summary, suggestions=suggestions, notion_urls=[])

# We start HTTP via the FastMCP CLI in Docker; don't start here.
if __name__ == "__main__":
    import os
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "3333"))
    print(f"[mcp] HTTP at http://{host}:{port}/mcp")
    mcp.run("http", host=host,port=port)
