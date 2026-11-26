"""Age verification adapters.

Self-declared date of birth is NOT enough in many jurisdictions (several US
states, the UK Online Safety Act, parts of the EU). In production, plug in a
real provider (Veriff, Yoti, Persona, etc.) that checks ID and/or does
facial age estimation, and only mark the user verified from the provider's
signed webhook.
"""

import uuid
from dataclasses import dataclass

from .config import settings


@dataclass
class VerificationStart:
    session_id: str
    redirect_url: str | None  # where to send the user to verify; None = done instantly (dev only)


class AgeVerifier:
    def start(self, user_id: int) -> VerificationStart:
        raise NotImplementedError

    def parse_webhook(self, headers: dict, body: bytes) -> tuple[str, bool]:
        """Validate the provider's signature and return (session_id, is_adult)."""
        raise NotImplementedError


class DevVerifier(AgeVerifier):
    """Development only: approves instantly. The app refuses to start with this in production."""

    def start(self, user_id: int) -> VerificationStart:
        return VerificationStart(session_id=f"dev-{uuid.uuid4()}", redirect_url=None)


class ProviderVerifier(AgeVerifier):
    """Template for a real provider. Fill in using your provider's API docs:
    1. start(): create a verification session via their API, return its id + hosted URL.
    2. parse_webhook(): verify the HMAC signature header with your secret, then read
       the decision and confirm the verified age is 18+.
    """

    def __init__(self, name: str, api_key: str):
        self.name = name
        self.api_key = api_key

    def start(self, user_id: int) -> VerificationStart:
        raise NotImplementedError(f"Connect the {self.name} API here (see its docs).")

    def parse_webhook(self, headers: dict, body: bytes) -> tuple[str, bool]:
        raise NotImplementedError(f"Verify {self.name} webhook signatures here.")


def get_verifier() -> AgeVerifier:
    if settings.age_verification_provider == "none":
        return DevVerifier()
    return ProviderVerifier(settings.age_verification_provider, settings.age_verification_api_key)
