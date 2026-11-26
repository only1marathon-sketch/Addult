import base64
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from . import billing
from .age_verification import get_verifier
from .auth import (age_on, create_token, get_current_user, hash_password,
                   require_verified_adult, verify_password)
from .config import assert_production_safe, settings
from .db import Base, engine, get_db
from .generation import chat_completion, generate_image, list_styles
from .models import GenerationLog, Report, User
from .safety import check_image, check_text

logging.basicConfig(level=logging.INFO)
assert_production_safe()
Base.metadata.create_all(engine)

app = FastAPI(title="Adult AI Platform", docs_url=None if settings.env == "production" else "/docs")

# Users who hit the minor filter this many times are suspended for human review.
BAN_THRESHOLD = 3
BLOCK_MESSAGE = "This request isn't allowed on this platform."


# ---------- Schemas ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    date_of_birth: date
    accept_terms: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ImageIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    negative_prompt: str = Field(default="", max_length=500)
    style: str | None = None
    aspect: str = Field(default="square", pattern="^(square|portrait|landscape)$")


ASPECTS = {"square": (1024, 1024), "portrait": (832, 1216), "landscape": (1216, 832)}


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


class ReportIn(BaseModel):
    generation_id: int | None = None
    reason: str = Field(min_length=3, max_length=2000)


# ---------- Helpers ----------
def record_block(db: Session, user: User, kind: str, prompt: str, category: str) -> GenerationLog:
    entry = GenerationLog(user_id=user.id, kind=kind, prompt=prompt, blocked=True, reason=category)
    db.add(entry)
    if category in ("minor", "possible_minor"):
        user.blocked_attempts += 1
        if user.blocked_attempts >= BAN_THRESHOLD:
            user.is_banned = True
            logging.getLogger("safety").warning("User %s suspended for review", user.id)
    db.commit()
    return entry


# ---------- Auth ----------
@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if not body.accept_terms:
        raise HTTPException(400, "You must accept the terms")
    if age_on(body.date_of_birth) < 18:
        raise HTTPException(403, "You must be 18 or older to use this service")
    if db.query(User).filter_by(email=body.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password),
                date_of_birth=body.date_of_birth, credits=settings.free_signup_credits)
    db.add(user)
    db.commit()
    return {"token": create_token(user.id)}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": create_token(user.id)}


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "age_verified": user.age_verified, "credits": user.credits}


# ---------- Age verification ----------
@app.post("/api/age-verification/start")
def start_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = get_verifier().start(user.id)
    user.verification_session_id = result.session_id
    if result.redirect_url is None:  # dev verifier approves instantly
        user.age_verified = True
        user.age_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"redirect_url": result.redirect_url, "age_verified": user.age_verified}


@app.post("/api/age-verification/webhook")
async def verification_webhook(request: Request, db: Session = Depends(get_db)):
    session_id, is_adult = get_verifier().parse_webhook(dict(request.headers), await request.body())
    user = db.query(User).filter_by(verification_session_id=session_id).first()
    if user is None:
        raise HTTPException(404, "Unknown session")
    if is_adult:
        user.age_verified = True
        user.age_verified_at = datetime.now(timezone.utc)
    else:
        user.is_banned = True
    db.commit()
    return {"ok": True}


# ---------- Generation ----------
@app.post("/api/generate/image")
async def create_image(body: ImageIn, user: User = Depends(require_verified_adult),
                       db: Session = Depends(get_db)):
    full_prompt = f"{body.prompt} {body.negative_prompt}"
    verdict = check_text(body.prompt)
    if not verdict.allowed:
        record_block(db, user, "image", full_prompt, verdict.category)
        raise HTTPException(400, BLOCK_MESSAGE)
    if user.credits < settings.image_cost:
        raise HTTPException(402, "Out of credits")

    try:
        width, height = ASPECTS[body.aspect]
        png = await generate_image(body.prompt, body.negative_prompt, body.style, width, height)
    except Exception:
        logging.exception("Image worker error")
        raise HTTPException(502, "Image generation failed, try again")

    img_verdict = check_image(png)
    if not img_verdict.allowed:
        record_block(db, user, "image", full_prompt, img_verdict.category)
        raise HTTPException(400, BLOCK_MESSAGE)

    user.credits -= settings.image_cost
    entry = GenerationLog(user_id=user.id, kind="image", prompt=full_prompt)
    db.add(entry)
    db.commit()
    return {"generation_id": entry.id, "image_b64": base64.b64encode(png).decode(), "credits": user.credits}


@app.post("/api/chat")
async def chat(body: ChatIn, user: User = Depends(require_verified_adult), db: Session = Depends(get_db)):
    latest = body.messages[-1].content
    verdict = check_text(latest)
    if not verdict.allowed:
        record_block(db, user, "chat", latest, verdict.category)
        raise HTTPException(400, BLOCK_MESSAGE)

    try:
        reply = await chat_completion([m.model_dump() for m in body.messages])
    except Exception:
        logging.exception("Chat server error")
        raise HTTPException(502, "Chat failed, try again")

    out_verdict = check_text(reply)
    if not out_verdict.allowed:
        db.add(GenerationLog(user_id=user.id, kind="chat", prompt=latest, blocked=True,
                             reason=f"output_{out_verdict.category}"))
        db.commit()
        reply = "Let's take the story in a different direction."

    entry = GenerationLog(user_id=user.id, kind="chat", prompt=latest)
    db.add(entry)
    db.commit()
    return {"generation_id": entry.id, "reply": reply}


# ---------- Reports & billing ----------
@app.post("/api/report")
def report(body: ReportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(Report(user_id=user.id, generation_id=body.generation_id, reason=body.reason))
    db.commit()
    return {"ok": True}


@app.post("/api/billing/webhook")
async def billing_webhook(request: Request, x_signature: str | None = Header(default=None),
                          db: Session = Depends(get_db)):
    parsed = billing.verify_and_parse(x_signature, await request.body())
    if parsed is None:
        raise HTTPException(400, "Invalid webhook")
    user_id, credits = parsed
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Unknown user")
    user.credits += credits
    db.commit()
    return {"ok": True}


@app.get("/api/styles")
async def styles(user: User = Depends(get_current_user)):
    return {"styles": await list_styles()}


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- Frontend ----------
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if not frontend_dir.exists():
    frontend_dir = Path("/app/frontend")
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
