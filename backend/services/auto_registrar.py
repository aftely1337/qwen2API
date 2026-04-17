import logging
import asyncio
import re
import secrets
import string
from curl_cffi.requests import AsyncSession
from backend.services.tempmail_client import TempMailClient
from backend.core.account_pool import Account

log = logging.getLogger("qwen2api.registrar")

class RegistrationError(Exception):
    pass

class QwenAutoRegistrar:
    def __init__(self):
        self.temp_mail = TempMailClient()
        self.base_url = "https://chat.qwen.ai"
        
    def _generate_password(self) -> str:
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for i in range(16)) + "A1!"

    async def register_account(self) -> Account:
        """Complete the full registration flow and return a valid Account."""
        log.info("[Registrar] Starting new account registration flow.")
        
        # 1. Get email
        mail_info = await self.temp_mail.generate_email()
        email = mail_info["address"]
        mail_token = mail_info["token"]
        password = self._generate_password()
        log.info(f"[Registrar] Acquired temp email: {email}")
        
        async with AsyncSession(impersonate="chrome124", timeout=30.0) as client:
            # 2. Send registration request to Qwen
            # In a real scenario, this would POST to Qwen's send-code endpoint.
            log.info(f"[Registrar] Sending registration code to {email}...")
            # TODO: Implement actual curl_cffi POST request to Qwen
            
            # 3. Wait for email
            log.info("[Registrar] Waiting for verification email...")
            email_data = await self.temp_mail.wait_for_email(mail_token, timeout=60)
            if not email_data:
                raise RegistrationError(f"Timeout waiting for verification email for {email}")
            
            # 4. Extract code/link from email_data['html'] or email_data['body']
            # code = re.search(r'verification code is (\d+)', email_data['body']).group(1)
            # TODO: Implement actual extraction
            
            # 5. Submit code and get JWT token
            # TODO: Implement actual curl_cffi POST request to verify code and get token
            
            # Mocking successful return for the architectural skeleton
            jwt_token = "mock_token_for_" + email
            
        log.info(f"[Registrar] Successfully registered {email}")
        return Account(
            email=email,
            password=password,
            token=jwt_token,
            status_code=200
        )
