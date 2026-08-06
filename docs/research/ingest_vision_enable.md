# ING-4 vision enable — operator checklist

**Status:** Code complete. **Final step:** install the model.

## When text PDF works (default)

- Upload `.pdf` with extractable text → `extract_pdf.py` (pypdf + LLM/deterministic).
- No vision model required.

## When you need scan/image PDFs

1. Confirm license note in `MEMORY.md` (Tongyi Qianwen / EU agreement).
2. Pull the model:
   ```bash
   ollama pull qwen3-vl:8b
   ```
3. Enable in API env:
   ```bash
   INGEST_VISION=ollama
   INGEST_VISION_MODEL=qwen3-vl:8b
   ```
4. Verify:
   ```bash
   curl -s http://127.0.0.1:8001/api/connections/{id}/ingest/vision/status
   ```
   Expect `"ready": true`.

## What happens

- Text-empty PDFs route to `extract_vision.py` → Ollama chat with image → same map/order/commit pipeline.
- Layout fingerprints cached in `ingest_layout_cache` for repeat supplier docs.
