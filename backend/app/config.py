from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"  # "development" or "production"
    secret_key: str = "change-me"
    database_url: str = "sqlite:///./data/app.db"

    # Internal services
    image_worker_url: str = "http://image-worker:8001"
    worker_token: str = "change-me-worker-token"
    chat_api_url: str = "http://chat:8000/v1"
    chat_model: str = "mistralai/Mistral-7B-Instruct-v0.3"

    # Safety providers. "none" is only allowed in development.
    age_verification_provider: str = "none"  # none | veriff | yoti
    age_verification_api_key: str = ""
    image_safety_provider: str = "none"  # none | rekognition
    aws_region: str = "us-east-1"
    min_estimated_age_low: int = 18  # block if any face's estimated lower age bound is below this
    celebrity_match_confidence: float = 80.0

    # Billing
    billing_webhook_secret: str = ""
    free_signup_credits: int = 5
    image_cost: int = 1


settings = Settings()


def assert_production_safe() -> None:
    """Refuse to start in production without real safety providers."""
    if settings.env != "production":
        return
    problems = []
    if settings.secret_key == "change-me":
        problems.append("SECRET_KEY is the default")
    if settings.worker_token == "change-me-worker-token":
        problems.append("WORKER_TOKEN is the default")
    if settings.age_verification_provider == "none":
        problems.append("AGE_VERIFICATION_PROVIDER is 'none'")
    if settings.image_safety_provider == "none":
        problems.append("IMAGE_SAFETY_PROVIDER is 'none'")
    if not settings.billing_webhook_secret:
        problems.append("BILLING_WEBHOOK_SECRET is empty")
    if problems:
        raise RuntimeError("Unsafe production config: " + "; ".join(problems))
