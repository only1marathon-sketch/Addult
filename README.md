# Adult AI Studio (18+)

A hosted, adults-only AI platform for **image generation** (SDXL + your own LoRA styles) and
**chat** (an open-source LLM served by vLLM), with age verification, content safety, credits and reporting.

```
Browser ──► backend (FastAPI, port 8080)  ──► image-worker (GPU, SDXL + LoRAs)
             │ auth · age check · filters  ──► chat (GPU, vLLM)
             │ credits · logs · reports    ──► AWS Rekognition (image safety)
             └ serves the frontend         ──► age-verification + payment providers
```

## Quick start (development)

```bash
cp .env.example .env          # leave providers as "none" for local testing
docker compose up --build     # needs a machine with NVIDIA GPU(s)
open http://localhost:8080
```

Without a GPU you can still run the backend and its tests:
```bash
cd backend && pip install -r requirements.txt && python -m pytest -q tests
uvicorn app.main:app --reload --port 8080
```

## Safety layers (all on by default)

| Layer | Where |
|---|---|
| 18+ date of birth at signup, plus age-gate splash | `main.py`, `frontend/` |
| Real age verification required before any generation | `age_verification.py` |
| Prompt and chat filter (minors, non-consent, real people), on input **and** model output | `safety/prompt_filter.py` |
| Default negative prompt against childlike output | `worker/server.py` |
| Every image checked for possible minors and celebrity faces before it's shown | `safety/image_checks.py` |
| Auto-suspend after repeated attempts involving minors | `main.py` (`BAN_THRESHOLD`) |
| No user photo uploads, so nobody can turn a real person's photo into explicit content | by design |
| Logs and user reports for review | `models.py` |
| Training blocked without documented adult consent | `training/check_dataset.py` |
| App **refuses to start in production** without real safety providers | `config.py` |

## Before you go live (checklist)

- [ ] Set `ENV=production`, random `SECRET_KEY` / `WORKER_TOKEN`, and switch to Postgres.
- [ ] Connect a real **age-verification provider** (Veriff, Yoti, Persona…) in `age_verification.py`.
- [ ] Turn on `IMAGE_SAFETY_PROVIDER=rekognition` (or Hive) and apply for **Thorn Safer / PhotoDNA** hash-matching.
- [ ] Add a vetted text-moderation classifier alongside the keyword filter.
- [ ] Set up a **high-risk payment processor** (CCBill, Segpay, Verotel) and adapt `billing.py` to its webhook signing.
- [ ] Put HTTPS in front (Caddy, Nginx or Cloudflare); keep worker and chat ports private.
- [ ] Write Terms, a Content Policy and a Privacy Policy (prompts are logged for abuse review).
- [ ] In the US, providers must report apparent child sexual abuse material to NCMEC (18 U.S.C. 2258A). Have a process for it.
- [ ] Check model licenses (SDXL: CreativeML Open RAIL++-M; Flux.1-dev is non-commercial) and your chat model's license.
- [ ] Have an adult-industry lawyer review age-verification, deepfake and record-keeping laws for every country you serve.

## Project layout

```
backend/    FastAPI app, safety, auth, billing, tests
worker/     GPU image server (diffusers)
frontend/   Web UI (age gate, sign-in, image studio, chat)
training/   LoRA training guide + dataset consent checker
loras/      Drop trained .safetensors style files here
```
