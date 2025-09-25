import os, datetime as dt
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from .kucoin_client import KucoinClient, KucoinBalance
from .notion_client import NotionClient
from .portfolio import aggregate_balances

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
    date_iso: str = Field(description="ISO date, e.g., 2025-09-24")
    note: str | None = None

class UpsertHoldingsOut(BaseModel):
    upserted: int

class ReportOut(BaseModel):
    as_of: str
    summary: str
    suggestions: list[str]
    notion_urls: list[str] = []

# ---------- Tool: health ----------
@mcp.tool
def health() -> HealthOut:
    return HealthOut(ok=True, version="0.2.0")

# Helpers to build clients
def _kc() -> KucoinClient:
    return KucoinClient(
        base_url=os.getenv("KUCOIN_BASE_URL", "https://api.kucoin.com"),
        api_key=os.environ["KUCOIN_API_KEY"],
        api_secret=os.environ["KUCOIN_API_SECRET"],
        api_passphrase=os.environ["KUCOIN_API_PASSPHRASE"],
    )

def _notion() -> NotionClient:
    return NotionClient(
        token=os.environ["NOTION_TOKEN"],
        database_id=os.environ["NOTION_DATABASE_ID"],
    )

# ---------- Tool: get_balances ----------
@mcp.tool
def get_balances() -> GetBalancesOut:
    """
    Fetch KuCoin balances from both 'main' and 'trade' accounts.
    """
    kc = _kc()
    main = kc.get_accounts("main")
    trade = kc.get_accounts("trade")
    # Include both; caller can aggregate
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return GetBalancesOut(as_of=now, balances=main + trade)

# ---------- Tool: upsert_holdings ----------
@mcp.tool
def upsert_holdings(args: UpsertHoldingsIn) -> UpsertHoldingsOut:
    """
    Aggregate balances and write one row per (asset, account, date) to Notion.
    """
    kc = _kc()
    n = _notion()

    # balances per account to keep account select accurate
    main = kc.get_accounts("main")
    trade = kc.get_accounts("trade")

    upserted = 0
    # write per account rows
    for b in main + trade:
        page_id = n.query_asset_on_date(b.currency, args.date_iso, b.accountType)
        n.create_or_update_balance(
            asset=b.currency,
            date_iso=args.date_iso,
            account=b.accountType,
            amount=b.available,
            holds=b.holds,
            balance=b.balance,
            total_spent=None,  # future step: cost basis ingestion
            notes=args.note,
            page_id=page_id,
        )
        upserted += 1

    return UpsertHoldingsOut(upserted=upserted)

# ---------- Tool: portfolio_report ----------
@mcp.tool
def portfolio_report() -> ReportOut:
    """
    Simple first-pass suggestions: flag concentrated positions, dust, and stablecoin mix.
    """
    kc = _kc()
    balances = kc.get_accounts("main") + kc.get_accounts("trade")
    positions = aggregate_balances(balances)

    total = sum(p.balance for p in positions)
    suggestions: list[str] = []
    # concentration
    for p in sorted(positions, key=lambda x: x.balance, reverse=True)[:5]:
        share = (p.balance / total * 100) if total else 0
        if share > 30:
            suggestions.append(f"{p.asset} is {share:.1f}% of portfolio — consider trimming.")
    # dust
    for p in positions:
        if 0 < p.balance < 5:
            suggestions.append(f"{p.asset} balance is small ({p.balance:.4f}); consider consolidating.")
    # stablecoin sanity
    stables = {"USDT", "USDC", "DAI", "FDUSD", "TUSD"}
    stable_sum = sum(p.balance for p in positions if p.asset in stables)
    if total:
        stable_share = stable_sum / total * 100
        if stable_share < 5:
            suggestions.append("Stablecoin buffer <5%; consider increasing dry powder.")
        elif stable_share > 40:
            suggestions.append("High stablecoin share (>40%); consider deploying if that’s unintentional.")

    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    summary = f"{len(positions)} assets; est. total units sum={total:.4f} (unit-sum across assets; USD valuation comes later)."
    return ReportOut(as_of=now, summary=summary, suggestions=suggestions, notion_urls=[])
    
if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "3333"))
    print(f"[mcp] HTTP at http://{host}:{port}/mcp")
    mcp.run(transport="http", host=host, port=port)
