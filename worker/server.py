"""GPU image worker. Internal only: never expose this port to the internet.

Loads an SDXL base model plus any LoRA style files in LORA_DIR
(e.g. /loras/glam.safetensors -> style "glam").
"""

import base64
import io
import os
import threading
from pathlib import Path

import torch
from diffusers import AutoPipelineForText2Image
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

BASE_MODEL = os.getenv("BASE_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
LORA_DIR = Path(os.getenv("LORA_DIR", "/loras"))
WORKER_TOKEN = os.environ["WORKER_TOKEN"]
STEPS = int(os.getenv("STEPS", "30"))

# Always added to the negative prompt as an extra layer against depicting minors.
SAFETY_NEGATIVE = "child, minor, teen, underage, childlike, young-looking, school uniform"

app = FastAPI()
lock = threading.Lock()

pipe = AutoPipelineForText2Image.from_pretrained(
    BASE_MODEL, torch_dtype=torch.float16, variant="fp16", use_safetensors=True
).to("cuda")

STYLES: list[str] = []
if LORA_DIR.exists():
    for f in sorted(LORA_DIR.glob("*.safetensors")):
        pipe.load_lora_weights(str(f), adapter_name=f.stem)
        STYLES.append(f.stem)


class GenerateIn(BaseModel):
    prompt: str = Field(max_length=1000)
    negative_prompt: str = Field(default="", max_length=500)
    style: str | None = None
    width: int = Field(default=1024, ge=512, le=1536)
    height: int = Field(default=1024, ge=512, le=1536)


@app.get("/styles")
def styles():
    return {"styles": STYLES}


@app.post("/generate")
def generate(body: GenerateIn, x_worker_token: str = Header(...)):
    if x_worker_token != WORKER_TOKEN:
        raise HTTPException(401, "Bad worker token")
    if body.style and body.style not in STYLES:
        raise HTTPException(400, f"Unknown style. Available: {STYLES}")

    negative = ", ".join(p for p in [SAFETY_NEGATIVE, body.negative_prompt] if p)
    with lock:
        if STYLES:
            if body.style:
                pipe.enable_lora()
                pipe.set_adapters([body.style], adapter_weights=[0.9])
            else:
                pipe.disable_lora()
        image = pipe(prompt=body.prompt, negative_prompt=negative, num_inference_steps=STEPS,
                     guidance_scale=6.5, width=body.width, height=body.height).images[0]

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return {"image_b64": base64.b64encode(buf.getvalue()).decode()}
