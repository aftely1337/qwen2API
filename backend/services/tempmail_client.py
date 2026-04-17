import httpx
import time
import asyncio
from typing import Dict, Any, Optional

class TempMailClient:
    def __init__(self):
        self.base_url = "https://tempmail.lol/api"
        self.client = httpx.AsyncClient(timeout=15.0)
    
    async def generate_email(self) -> Dict[str, str]:
        """Returns {"address": "...", "token": "..."}"""
        resp = await self.client.get(f"{self.base_url}/auth/create")
        resp.raise_for_status()
        data = resp.json()
        return {
            "address": data.get("address"),
            "token": data.get("token")
        }
    
    async def check_inbox(self, token: str) -> list[Dict[str, Any]]:
        """Check emails for a given token."""
        resp = await self.client.get(f"{self.base_url}/auth/check", headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 404:
            return [] # Invalid or expired
        resp.raise_for_status()
        return resp.json().get("emails", [])

    async def wait_for_email(self, token: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """Poll the inbox until an email arrives or timeout occurs."""
        start = time.time()
        while time.time() - start < timeout:
            emails = await self.check_inbox(token)
            if emails:
                return emails[0]
            await asyncio.sleep(3)
        return None
