import asyncio
import time
from typing import Any, Dict, Optional

import httpx


class TempMailClient:
    def __init__(self):
        self.base_url = "https://api.tempmail.lol/v2"
        self.client = httpx.AsyncClient(timeout=15.0)

    async def generate_email(self, prefix: Optional[str] = None, domain: Optional[str] = None) -> Dict[str, str]:
        """Returns {"address": "...", "token": "..."}."""
        payload: Dict[str, str] = {}
        if prefix:
            payload["prefix"] = prefix
        if domain:
            payload["domain"] = domain

        resp = await self.client.post(f"{self.base_url}/inbox/create", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "address": data.get("address"),
            "token": data.get("token"),
        }

    async def check_inbox(self, token: str) -> list[Dict[str, Any]]:
        """Check emails for a given token."""
        resp = await self.client.get(f"{self.base_url}/inbox?token={token}")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        if data.get("expired"):
            return []
        return data.get("emails", [])

    async def wait_for_email(self, token: str, timeout: int = 60, poll_interval: float = 3.0) -> Optional[Dict[str, Any]]:
        """Poll the inbox until an email arrives or timeout occurs."""
        start = time.time()
        while time.time() - start < timeout:
            emails = await self.check_inbox(token)
            if emails:
                return emails[0]
            await asyncio.sleep(poll_interval)
        return None
