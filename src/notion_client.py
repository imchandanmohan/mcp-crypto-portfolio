from typing import Any, Dict, Optional, List
import httpx
from pydantic import BaseModel

def _notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

class NotionPageRef(BaseModel):
    id: str
    url: str

class NotionClient:
    def __init__(self, token: str, database_id: str) -> None:
        self.token = token
        self.database_id = database_id

    def query_asset_on_date(self, asset: str, date_iso: str, account: str) -> Optional[str]:
        body = {
            "filter": {
                "and": [
                    {"property": "Asset", "title": {"equals": asset}},
                    {"property": "Date", "date": {"equals": date_iso}},
                    {"property": "Account", "select": {"equals": account}},
                ]
            },
            "page_size": 1,
        }
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                "https://api.notion.com/v1/databases/{}/query".format(self.database_id),
                headers=_notion_headers(self.token),
                json=body,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if results:
                return results[0]["id"]
        return None

    def create_or_update_balance(
        self,
        asset: str,
        date_iso: str,
        account: str,
        amount: float,
        holds: float,
        balance: float,
        total_spent: float | None = None,
        notes: str | None = None,
        page_id: str | None = None
    ) -> NotionPageRef:
        props: Dict[str, Any] = {
            "Asset": {"title": [{"text": {"content": asset}}]},
            "Date": {"date": {"start": date_iso}},
            "Account": {"select": {"name": account}},
            "Amount": {"number": amount},
            "Holds": {"number": holds},
            "Balance": {"number": balance},
        }
        if total_spent is not None:
            props["TotalSpent"] = {"number": total_spent}
        if notes:
            props["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

        with httpx.Client(timeout=20.0) as client:
            if page_id:
                r = client.patch(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=_notion_headers(self.token),
                    json={"properties": props},
                )
            else:
                r = client.post(
                    "https://api.notion.com/v1/pages",
                    headers=_notion_headers(self.token),
                    json={"parent": {"database_id": self.database_id}, "properties": props},
                )
            r.raise_for_status()
            j = r.json()
            return NotionPageRef(id=j["id"], url=j["url"])
