# Training your own styles

## Image styles (LoRA on SDXL)

1. Put licensed images in `training/dataset/`, each with a same-name `.txt` caption.
2. Fill in `training/manifest.csv` (see `check_dataset.py` for the columns).
3. **Run the consent check. Do not train if it fails:**
   ```bash
   python training/check_dataset.py training/dataset training/manifest.csv
   ```
4. Train with the official Hugging Face diffusers script on a rented GPU (24 GB+ VRAM):
   ```bash
   git clone https://github.com/huggingface/diffusers && cd diffusers/examples/text_to_image
   pip install -r requirements_sdxl.txt
   accelerate launch train_text_to_image_lora_sdxl.py \
     --pretrained_model_name_or_path=stabilityai/stable-diffusion-xl-base-1.0 \
     --train_data_dir=../../../training/dataset \
     --resolution=1024 --train_batch_size=1 --gradient_accumulation_steps=4 \
     --max_train_steps=2000 --learning_rate=1e-4 --mixed_precision=fp16 \
     --output_dir=../../../training/output/mystyle
   ```
   Check the script's own README for the current flags.
5. Copy `training/output/mystyle/pytorch_lora_weights.safetensors` to `loras/mystyle.safetensors`
   and restart the image worker. It will show up as style `mystyle`.

## Chat model

Set `CHAT_MODEL` in `.env` to any model whose license allows your use. To fine-tune on your
own writing, use a LoRA trainer such as Hugging Face TRL or Axolotl, then serve the merged model
with vLLM. Only use text you own or have licensed, and keep the system prompt in
`backend/app/generation.py`.

## Rules for training data
- Only adults (18+ at the time of capture) with verified ID and a signed release that covers AI training.
- No images of real public figures or anyone who hasn't consented.
- Never scrape adult sites. Scraped data has unknown ages and no consent.
