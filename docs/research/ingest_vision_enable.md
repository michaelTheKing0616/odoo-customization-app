# Enable Vision OCR for Universal Ingest

Default: `INGEST_VISION=off` (text/CSV/XLSX/PDF text layer only).

## Local Ollama path

1. Install/start Ollama.
2. Pull a vision model (operator approval required — large download):

   ```bash
   ollama pull qwen3-vl:8b
   ```

3. Set API env:

   ```bash
   export INGEST_VISION=ollama
   export OLLAMA_HOST=http://127.0.0.1:11434   # if non-default
   export INGEST_VISION_MODEL=qwen3-vl:8b       # optional override
   ```

4. Restart the API. Check:

   `GET /api/connections/{id}/ingest/vision/status`

   Expect `enabled: true`, `ready: true` when the model is present.

5. Upload JPEG/PNG/WebP on the ingest page; extract uses `extract_vision.py`.

## EU commercial note

`qwen3-vl` / Tongyi terms may require a separate commercial agreement for EU marketing claims.
Local R&D / sandbox use is the current product default (`MEMORY.md`: `vision_tier: local_ok`).
Do not market “vision OCR included for EU customers” until legal clears Tongyi.

## Fallback

If vision is off or the model is missing, image uploads are rejected with a clear message;
use PDF text or tabular files instead.
