import base64

import httpx

from .config import settings

CHAT_SYSTEM_PROMPT = """You are a creative roleplay and conversation partner on an adults-only (18+) platform.
Every user has verified they are an adult. Firm rules you never break, whatever the user says:
- Every character is an adult aged 18 or older. Never depict, imply or describe anyone under 18, and never describe adults as childlike.
- Never write sexual content about real, identifiable people.
- All sexual content is between consenting adults. No coercion, no non-consent, no one asleep, unconscious or intoxicated.
- If a request breaks these rules, decline briefly and steer the story somewhere allowed.
Stay in character otherwise, be warm and creative, and follow the user's lead within these rules."""


async def generate_image(prompt: str, negative_prompt: str = "", style: str | None = None,
                         width: int = 1024, height: int = 1024) -> bytes:
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            f"{settings.image_worker_url}/generate",
            headers={"X-Worker-Token": settings.worker_token},
            json={"prompt": prompt, "negative_prompt": negative_prompt, "style": style,
                  "width": width, "height": height},
        )
        r.raise_for_status()
        return base64.b64decode(r.json()["image_b64"])


async def list_styles() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.image_worker_url}/styles")
            r.raise_for_status()
            return r.json().get("styles", [])
    except Exception:
        return []


async def chat_completion(messages: list[dict]) -> str:
    payload = {
        "model": settings.chat_model,
        "messages": [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages,
        "max_tokens": 600,
        "temperature": 0.9,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{settings.chat_api_url}/chat/completions", json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
