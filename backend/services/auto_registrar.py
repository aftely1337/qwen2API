import hashlib
import html as html_lib
import json
import logging
import re
import secrets
import string
from typing import Any, Optional

import httpx
from curl_cffi.requests import AsyncSession

from backend.core.account_pool import Account
from backend.core.browser_engine import _new_browser
from backend.services.tempmail_client import TempMailClient

log = logging.getLogger("qwen2api.registrar")

DEFAULT_CTF_JSHOOK = '(function(){ console.log("CTF environment verified"); })();'
QWEN_PROFILE_IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAF80lEQVR4Aeyae2wURRzHv7d3vWvvmhYMVRD/UdFCIqJoDFGRmGgwxD8MwUciPppgJNFgDCbyR40QH5iohCo1JcVXND5A/c8QtVSNtor4qq9EQI0Ipailr7tr7+3+rp0eaJncbjqzs+evyWRudx6/2c9nZ7e7O1bT6v4CJ3MYWOA/owiwEKN0ACyEhRhGwLDh8AxhIYYRMGw4PENYiGEEDBsOz5D/hRDDDtJPw+EZYpgtFsJCDCNg2HB4hrAQwwgYNhyeISzEMAKGDYdnCAsxjIBhw/HTDDEMnZrhsBA1XF33ykJco1PTkIWo4eq6VxbiGp2ahixEDVfXvbIQ1+jUNGQhari67pWFuEanpiELUcPVda8sxDU6NQ1ZiBqurntlIa7RqWnIQtRwdd0rC3GNTk1D3wtZdnUE6+6vxeNP1qN1+0w81z6enm6ZgXvvq8WSy8NqyCnq1ZdCqqsDuOXWKLa2zsDtTTFctDiM2bODqIkGQGWUZp5mYfGlYdy1thabbVlLl0UUIZzebn0n5IKFVWjeWIdrl1ejrs5CICAHQuVn2LJuuzOGpjWxojB5C29LLW/DO4tOZ/matTGcOTd4koh8Dvjrzzx6vsmguyuFLz5Po/dIDplMYTJAKARcsTQCaj+508AfvhGycFEVblhZU5wVgmM2C3z9ZRqbHx3Gg+sH0bJlBDvaEmhrjaN5wxA2PDCEvbYcIWZsrIAfvsuI5kbmvhBC94dVN0VB9wVBMZksYOfrSWxrieOXg7YZUXBCPnA8j+22nF1vjGJgII/OjjF81Jk6oYayn647tly31NjwmuURzD0rOBlx1Jbx9s4kOt4fm9wn+0H11q8bxDu7RmXVjCgzXsi580K4cFEY1sRIC/ZtoefbDD7cY/aZ7tbuxGG6ba6+3cWXhE+6VB3vz2PPB+XNDPWjm/4IxguZd14IwYmrFc2Ogweyp7xnTD8e/T0aLeT8xhAaGkpDTKcLICH6MemLWDpafTHLjkQPdFH76Vs0SCYK+OPQ1P9RiTp+z40WMmuWhWCo9Cg+OlrA/p9ZiGcnXV29LSRYCj84mC9tVOgvo2cI/atL76IqlP2Uh2W0kClHXOE7pUIq/NiNPDyjhdBLQXr2EOTC4dINXuyrtNxoIYl4ATn71bqAHosFQB+fxHYl5kYLOXo0h4z9MCjAx2oDmL/A/rAhdlRgbrSQY315JOw3u4J7NGrh7HNYiOChPf/t1yx6D5euWfTVr3FBlfZx6Axo9AwhEAf2Z0E3d/pNib6L+G0lCY273GS8kK/2pdH/d+kJnW7s9G29Um/uxgvp68th39406Pu5OMsa51dh9R1RsVlWvvLGmuJyIPo2X1YDjyoZL4S47H53zH6pmIF4JqFXKpctiZS1rIdmEi3/uW5FDejt8aqbo8VVK9SvicnSPyjnEWm1yGuvJHH4Xzf4K6+KYNNj9VhxffV/nk9IBO2ncqpH/xBQ5DlzgkavZvSFEALZeySHt95M4ph9CaNtSvTiseF0C3TWb2sbX0IqlpLSNu2ncqpH9emy1/1pyujFDr4RQkC/78ng2a1x/PRjBrQ4jvaJZNmv6WlWiETboozy4eE8aKXKS88naNPY5CshRJFmylNPjOCF9gToOYXOetp/qkRLhj7rSmPTQ8N4b7f5iyN8J0SA7+5K4ZGHx1csvrgjgU8+ThWXkh76PVdczdjZkULrM3Hcc/cA2tvioEVzoq3JuW+FCKgEmmSQlJYtI9jYPFRczfjqywnQM4yo55fc90L8ArrccbKQcklpqsdCNIEuNwwLKZeUpnoVI0QTL+VhWIhyxM4CsBBnvJTXZiHKETsLwEKc8VJem4UoR+wsAAtxxkt5bRaiHLGzACzEGS/ltVmIcsTOArAQKS/9hSxEP3NpRBYixaO/kIXoZy6NyEKkePQXshD9zKURWYgUj/5CFqKfuTQiC5Hi0V/IQvQzl0ZkIVI8agplvbIQGR0PyliIB9BlIVmIjI4HZSzEA+iykCxERseDMhbiAXRZSBYio+NBGQvxALos5D8AAAD//z2Tl4EAAAAGSURBVAMAzJBe62QKyQoAAAAASUVORK5CYII="
)

JS_SIGNUP = """
async (args) => {
  try {
    if (args.jshook) {
      try { (new Function(args.jshook))(); } catch (e) { console.warn('jshook failed', e); }
    }
    const resp = await fetch('/api/v1/auths/signup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'source': 'web',
        'version': args.version,
        'bx-v': args.bxv
      },
      body: JSON.stringify(args.payload)
    });
    const text = await resp.text();
    let data = null;
    try { data = JSON.parse(text); } catch (e) {}
    return {
      status: resp.status,
      text,
      data,
      token: (data && (data.token || (data.data && data.data.token))) || localStorage.getItem('token'),
      location: location.href
    };
  } catch (e) {
    return { status: 0, error: String(e) };
  }
}
"""


class RegistrationError(Exception):
    pass


class QwenAutoRegistrar:
    def __init__(self, temp_mail: Optional[TempMailClient] = None, jshook: str = DEFAULT_CTF_JSHOOK):
        self.temp_mail = temp_mail or TempMailClient()
        self.base_url = "https://chat.qwen.ai"
        self.jshook = jshook
        self.version = "0.2.40"
        self.bxv = "2.5.36"

    def _generate_password(self) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(16)) + "A1!"

    def _generate_name(self) -> str:
        return f"CTF Auto {secrets.token_hex(3)}"

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _build_signup_payload(self, email: str, password: str, name: str) -> dict[str, Any]:
        return {
            "name": name,
            "email": email,
            "password": self._hash_password(password),
            "agree": True,
            "profile_image_url": QWEN_PROFILE_IMAGE,
            "oauth_sub": "",
            "oauth_token": "",
            "module": "chat",
        }

    def _build_auth_headers(self, token: Optional[str] = None) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": f"{self.base_url}/",
            "Origin": self.base_url,
            "source": "web",
            "version": self.version,
            "bx-v": self.bxv,
            "timezone": "Fri Apr 17 2026 13:10:30 GMT+0800",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _extract_activation_link(self, email_data: dict[str, Any]) -> str:
        subject = str(email_data.get("subject", ""))
        raw_parts = []
        for field in ("html", "body", "text", "content"):
            value = email_data.get(field)
            if value:
                raw_parts.append(str(value))

        raw = html_lib.unescape(" ".join(raw_parts))
        raw = raw.replace("\\/", "/")

        href_links = re.findall(r'href=["\'](https?://[^"\']+)["\']', raw, flags=re.IGNORECASE)
        text_links = re.findall(r"https?://[^\s\"'<>]+", raw, flags=re.IGNORECASE)
        candidates = href_links + text_links
        for link in candidates:
            cleaned = link.rstrip(".,;)")
            if "/api/v1/auths/activate" in cleaned and "chat.qwen.ai" in cleaned:
                return cleaned

        if "active" in subject.lower() or "activate" in subject.lower():
            for link in candidates:
                cleaned = link.rstrip(".,;)")
                if "chat.qwen.ai" in cleaned:
                    return cleaned
        return ""

    async def _signup_with_browser(self, payload: dict[str, Any]) -> dict[str, Any]:
        log.info("[Registrar] Submitting signup request through browser fetch.")
        async with _new_browser() as browser:
            page = await browser.new_page()
            await page.goto(f"{self.base_url}/auth?action=signup", wait_until="domcontentloaded", timeout=60000)
            result = await page.evaluate(
                JS_SIGNUP,
                {
                    "payload": payload,
                    "jshook": self.jshook,
                    "version": self.version,
                    "bxv": self.bxv,
                },
            )
            try:
                cookies = await page.context.cookies()
            except Exception:
                cookies = []

        if not isinstance(result, dict):
            raise RegistrationError(f"Unexpected signup result: {result!r}")
        if result.get("status") != 200:
            raise RegistrationError(
                f"Signup failed: status={result.get('status')} body={(result.get('text') or result.get('error') or '')[:300]}"
            )

        data = result.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = None

        if not isinstance(data, dict):
            body = (result.get("text") or "")[:300]
            raise RegistrationError(f"Signup returned non-JSON response: {body}")

        token = data.get("token") or result.get("token")
        if not token:
            raise RegistrationError(f"Signup succeeded but token is missing: {json.dumps(data, ensure_ascii=False)[:500]}")

        cookie_str = "; ".join(
            f"{cookie.get('name', '')}={cookie.get('value', '')}"
            for cookie in cookies
            if "qwen.ai" in cookie.get("domain", "")
        )
        return {
            "data": data,
            "token": token,
            "cookies": cookie_str,
        }

    async def _activate_account(self, activation_link: str) -> None:
        log.info("[Registrar] Visiting activation link.")
        async with AsyncSession(impersonate="chrome124", timeout=30.0, verify=False) as client:
            resp = await client.get(activation_link, headers=self._build_auth_headers(), allow_redirects=True)
        if resp.status_code != 200:
            raise RegistrationError(f"Activation failed: HTTP {resp.status_code}: {resp.text[:200]}")

    async def _fetch_auth_profile(self, token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(f"{self.base_url}/api/v1/auths/", headers=self._build_auth_headers(token))
        resp.raise_for_status()
        return resp.json()

    async def _verify_activated_user(self, token: str, attempts: int = 10) -> dict[str, Any]:
        import asyncio

        last_profile: dict[str, Any] = {}
        for _ in range(attempts):
            profile = await self._fetch_auth_profile(token)
            last_profile = profile
            if profile.get("role") == "user":
                return profile
            await asyncio.sleep(1)
        raise RegistrationError(
            f"Account activation did not complete in time. Last role={last_profile.get('role')!r}"
        )

    async def register_account(self) -> Account:
        """Complete the full registration flow and return an activated Account."""
        log.info("[Registrar] Starting new account registration flow.")

        mail_info = await self.temp_mail.generate_email(prefix=f"ctf{secrets.token_hex(3)}")
        email = mail_info["address"]
        mail_token = mail_info["token"]
        password = self._generate_password()
        username = self._generate_name()
        signup_payload = self._build_signup_payload(email=email, password=password, name=username)
        log.info(f"[Registrar] Acquired temp email: {email}")

        signup = await self._signup_with_browser(signup_payload)
        jwt_token = signup["token"]
        cookies = signup.get("cookies", "")
        role = signup.get("data", {}).get("role")
        if role == "user":
            profile = await self._verify_activated_user(jwt_token, attempts=1)
            log.info(f"[Registrar] Successfully registered {email} without email activation.")
            return Account(
                email=email,
                password=password,
                token=jwt_token,
                cookies=cookies,
                username=username,
                activation_pending=False,
                status_code="valid",
                last_error="",
            )

        log.info(f"[Registrar] Signup succeeded for {email}; waiting for activation email.")

        email_data = await self.temp_mail.wait_for_email(mail_token, timeout=60)
        if not email_data:
            raise RegistrationError(f"Timeout waiting for verification email for {email}")

        activation_link = self._extract_activation_link(email_data)
        if not activation_link:
            raise RegistrationError(f"Failed to extract activation link for {email}")

        await self._activate_account(activation_link)
        profile = await self._verify_activated_user(jwt_token)
        log.info(f"[Registrar] Successfully registered {email} with role={profile.get('role')}")

        return Account(
            email=email,
            password=password,
            token=jwt_token,
            cookies=cookies,
            username=username,
            activation_pending=False,
            status_code="valid",
            last_error="",
        )
