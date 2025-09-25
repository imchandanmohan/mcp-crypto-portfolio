from typing import List, Dict
from pydantic import BaseModel
from .kucoin_client import KucoinBalance

class AggregatedPosition(BaseModel):
    asset: str
    amount: float      # sum available
    holds: float       # sum holds
    balance: float     # sum balance
    accounts: Dict[str, float]  # per account balance

def aggregate_balances(balances: List[KucoinBalance]) -> List[AggregatedPosition]:
    by_symbol: Dict[str, AggregatedPosition] = {}
    for b in balances:
        ap = by_symbol.get(b.currency)
        if not ap:
            ap = AggregatedPosition(asset=b.currency, amount=0.0, holds=0.0, balance=0.0, accounts={})
            by_symbol[b.currency] = ap
        ap.amount += b.available
        ap.holds += b.holds
        ap.balance += b.balance
        ap.accounts[b.accountType] = ap.accounts.get(b.accountType, 0.0) + b.balance
    # filter dust-zero
    return [p for p in by_symbol.values() if p.balance > 0 or p.holds > 0 or p.amount > 0]
