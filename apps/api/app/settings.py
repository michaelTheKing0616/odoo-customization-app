from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILES = (
    str(_REPO_ROOT / ".env"),
    ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App metadata DB (separate from customer Odoo DBs)
    database_url: str = (
        "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom"
    )
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str = "dev-only-replace-me-use-Fernet-generate_key()"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    odoo_url: str = "http://127.0.0.1:8069"
    odoo_db: str = "odoo_dev"
    odoo_user: str = "admin"
    odoo_password: str = "admin"

    # Phase 7 — app API auth
    # off: no checks (local gates / tests)
    # api_key: require Bearer / X-API-Key matching APP_API_KEY or hashed keys in DB
    # accounts: session cookie (web) with optional API key fallback for CI
    auth_mode: str = "off"
    # Bootstrap / env key (plaintext). Preferred for single-operator deploy.
    app_api_key: str | None = None
    # Mutating requests per client IP per minute (0 = disabled)
    rate_limit_per_minute: int = 120
    # Persist mutating request audit rows
    audit_log_enabled: bool = True
    # Max age (days) for audit rows; purge endpoint / startup trim uses this (0 = never)
    audit_retention_days: int = 90
    # Honour X-Forwarded-For only when behind a trusted reverse proxy
    trusted_proxy: bool = False
    # Soft warn in /health when AUTH_MODE=off (deploy checklist)
    warn_auth_off: bool = True
    # Comma-separated modules to install in sandbox after DB init (e.g. sale,account).
    # Empty = fast smoke; extension gates set SANDBOX_EXTRA_MODULES=sale,account.
    sandbox_extra_modules: str = ""
    # Ephemeral sandbox from containerized API: path to Docker socket, or empty = disabled.
    # Deploy profile defaults off; mount /var/run/docker.sock and set this to enable.
    sandbox_docker_socket: str = ""
    # off | auto — auto runs alembic upgrade head on startup (deploy profile)
    db_migrations: str = "off"
    # Phase P3 — NL → ModuleSpec
    # off | ollama | openai-compatible
    ai_assist: str = "off"
    ollama_base_url: str = "http://127.0.0.1:11434"
    # Prefer qwen2.5 7B Q4 on Apple Silicon; override via OLLAMA_MODEL
    ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"
    # Per-step model ladder (empty = fall back to ollama_model / openai_compatible_model)
    ai_model_bulk: str = "qwen3:8b"
    ai_model_reasoning: str = "qwen3:14b"
    # auto | on | off — native Ollama `think` when model supports it; else manual CoT
    ai_thinking: str = "auto"
    # Per-step model ladder (empty = fall back to ollama_model / openai_compatible_model)
    ai_model_bulk: str = "qwen3:8b"
    ai_model_reasoning: str = "qwen3:14b"
    # auto | on | off — native Ollama `think` when model supports it; else manual CoT
    ai_thinking: str = "auto"
    # OpenAI-compatible (vLLM / LM Studio / OpenAI / Groq)
    openai_compatible_base_url: str = ""
    openai_compatible_model: str = "gpt-4o-mini"
    openai_compatible_api_key: str | None = None
    # single | staged — staged = Step 0–6 pipeline when LLM available
    ai_pipeline_mode: str = "single"
    # Domain pack RAG: auto|on|off — embeddings when sentence-transformers installed
    ai_rag: str = "auto"
    ai_rag_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ai_rag_min_score: float = 0.35
    # Self-critique pass after draft: auto|on|off
    ai_critique: str = "auto"
    # Self-consistency vote/merge on scaffold + workflow steps: off|on (default off)
    ai_self_consistency: str = "off"
    # Expert RAG (EXP-1) — community Q&A: off | dir (reads expert_community_dir)
    expert_community_source: str = "off"
    expert_community_dir: str = ""

    # MON-1 — accounts auth (when AUTH_MODE=accounts)
    app_public_url: str = "http://localhost:3000"
    session_cookie_secure: bool = False
    email_transport: str = "console"  # console | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # OAuth (MON-1) — off by default; [SKIPPED] implementation until configured
    oauth_providers: str = ""

    app_admin_email: str = ""
    app_admin_password: str = ""

    # MON-2 — billing (Stripe + Paystack)
    billing_mode: str = "off"  # off | fake | live
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_business: str = ""
    stripe_price_agency: str = ""
    stripe_price_project_pass: str = ""
    paystack_secret_key: str = ""
    paystack_price_pro_kobo: int = 0
    paystack_price_business_kobo: int = 0
    business_trial_enabled: bool = True
    business_trial_days: int = 14

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def auth_enabled(self) -> bool:
        return self.auth_mode.strip().lower() in {"api_key", "on", "true", "1"}

    @property
    def accounts_auth_enabled(self) -> bool:
        return self.auth_mode.strip().lower() == "accounts"

    def stripe_price_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.stripe_price_pro:
            out["pro"] = self.stripe_price_pro
        if self.stripe_price_business:
            out["business"] = self.stripe_price_business
        if self.stripe_price_agency:
            out["agency"] = self.stripe_price_agency
        if self.stripe_price_project_pass:
            out["project_pass"] = self.stripe_price_project_pass
        return out

    def sandbox_extra_module_list(self) -> list[str]:
        return [m.strip() for m in self.sandbox_extra_modules.split(",") if m.strip()]

    @property
    def sandbox_docker_enabled(self) -> bool:
        return bool(self.sandbox_docker_socket.strip())


settings = Settings()
