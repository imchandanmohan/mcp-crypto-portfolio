import base64, hashlib, hmac, json, time
from typing import Dict, Any, List
import httpx
from pydantic import BaseModel

class KucoinBalance(BaseModel):
    currency: str
    available: float
    holds: float
    balance: float
    accountType: str  # "main" or "trade"

class KucoinClient:
    def __init__(self, base_url: str, api_key: str, api_secret: str, api_passphrase: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.api_passphrase = api_passphrase

    def _sign(self, method: str, path: str, body: Dict[str, Any] | None = None) -> Dict[str, str]:
        ts = str(int(time.time() * 1000))
        body_str = json.dumps(body) if (body and method.upper() != "GET") else ""
        prehash = ts + method.upper() + path + body_str
        sign = base64.b64encode(hmac.new(self.api_secret, prehash.encode(), hashlib.sha256).digest()).decode()
        passphrase = base64.b64encode(hmac.new(self.api_secret, self.api_passphrase.encode(), hashlib.sha256).digest()).decode()
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": sign,
            "KC-API-TIMESTAMP": ts,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_accounts(self, account_type: str | None = None) -> List[KucoinBalance]:
        """
        account_type: "main", "trade", or None for all.
        """
        path = "/api/v1/accounts"
        query = f"?type={account_type}" if account_type else ""
        headers = self._sign("GET", path + query)
        with httpx.Client(timeout=20.0) as client:
            r = client.get(self._url(path + query), headers=headers)
            r.raise_for_status()
            data = r.json().get("data", [])
        out: List[KucoinBalance] = []
        for item in data:
            out.append(
                KucoinBalance(
                    currency=item["currency"],
                    available=float(item["available"]),
                    holds=float(item["holds"]),
                    balance=float(item["balance"]),
                    accountType=item["type"],  # "main" or "trade"
                )
            )
        return out
