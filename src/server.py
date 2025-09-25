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
    date_iso: str = Field(..., description="ISO date, e.g., 2025-09-24")
    note: str | None = None

class UpsertHoldingsOut(BaseModel):
    as_of: str
    message: str

class ReportOut(BaseModel):
    as_of: str
    summary: str
    suggestions: list[str]
    notion_urls: list[str]

# ---------- Tools ----------

@mcp.tool()
def health() -> HealthOut:
    """Health check for the MCP server."""
    return HealthOut(ok=True, version="0.1.0")

@mcp.tool()
def get_balances() -> GetBalancesOut:
    """Fetch KuCoin balances from both 'main' and 'trade' accounts."""
    client = KucoinClient()
    balances = client.get_all_balances()
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return GetBalancesOut(as_of=now, balances=balances)

@mcp.tool()
def upsert_holdings(args: UpsertHoldingsIn) -> UpsertHoldingsOut:
    """Aggregate balances and write one row per (asset, account, date) to Notion."""
    client = KucoinClient()
    balances = client.get_all_balances()
    
    # Aggregate by asset+account
    aggregated = aggregate_balances(balances, args.date_iso, args.note)
    
    # Write to Notion
    notion_client = NotionClient()
    results = []
    for holding in aggregated:
        result = notion_client.upsert_holding(holding)
        results.append(result)
    
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return UpsertHoldingsOut(
        as_of=now,
        message=f"Upserted {len(results)} holdings to Notion for date {args.date_iso}"
    )

@mcp.tool()
def portfolio_report() -> ReportOut:
    """Simple first-pass suggestions: flag concentrated positions, dust, and stablecoin mix."""
    client = KucoinClient()
    balances = client.get_all_balances()
    
    # Convert to positions for analysis
    positions = []
    for bal in balances:
        if bal.balance > 0:
            positions.append(bal)
    
    suggestions = []
    
    # concentration risk
    if len(positions) > 0:
        positions_sorted = sorted(positions, key=lambda x: x.balance, reverse=True)
        total = sum(p.balance for p in positions)
        
        if total > 0:
            top_asset = positions_sorted[0]
            top_share = top_asset.balance / total * 100
            if top_share > 50:
                suggestions.append(f"High concentration in {top_asset.asset} ({top_share:.1f}%); consider diversifying.")
        
        # dust cleanup
        dust_threshold = 0.001
        dust_count = sum(1 for p in positions if p.balance < dust_threshold)
        if dust_count > 5:
            suggestions.append(f"{dust_count} micro-positions detected; consider cleanup.")
    
    # Calculate total for stablecoin analysis
    total = sum(p.balance for p in positions) if positions else 0
    
    # stablecoin sanity
    stables = {"USDT", "USDC", "DAI", "FDUSD", "TUSD"}
    stable_sum = sum(p.balance for p in positions if p.asset in stables)
    if total:
        stable_share = stable_sum / total * 100
        if stable_share < 5:
            suggestions.append("Stablecoin buffer <5%; consider increasing dry powder.")
        elif stable_share > 40:
            suggestions.append("High stablecoin share (>40%); consider deploying if that's unintentional.")

    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    summary = f"{len(positions)} assets; est. total units sum={total:.4f} (unit-sum across assets; USD valuation comes later)."
    return ReportOut(as_of=now, summary=summary, suggestions=suggestions, notion_urls=[])
    
if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "3333"))
    print(f"[mcp] HTTP at http://{host}:{port}/mcp")
    mcp.run(transport="http", host=host, port=port)