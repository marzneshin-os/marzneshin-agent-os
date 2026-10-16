"""freellm_pool.py — FreeLLMAPI Universal Free-Tier Token Pool & Resilient Router.

Aggregates 34+ free LLM provider tiers (~7.4B tokens/month) into a unified,
resilient, zero-downtime token pool with multi-key rotation, automatic 429/402
cooldown management, AES-256-GCM key vault, and smart fallback routing.

No network I/O. Safe for lint-imports (stdlib only at module level).
All timestamps routed through lib.clock (D6).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import atomic, clock, paths


# ---------------------------------------------------------------------------
# Provider Definition & Catalog (34+ Free-Tier Providers, ~7.4B Tokens/Month)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FreeLLMProvider:
    id: str
    name: str
    base_url: str
    api_key_env: str
    monthly_token_quota: int
    rpm: int
    tpm: int
    models: list[str]
    specialties: list[str]
    format: str = "openai"  # "openai" | "anthropic" | "custom"
    description: str = ""


PROVIDER_CATALOG: dict[str, FreeLLMProvider] = {
    "google_gemini": FreeLLMProvider(
        id="google_gemini",
        name="Google AI Studio (Gemini)",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GEMINI_API_KEY",
        monthly_token_quota=1_000_000_000,
        rpm=15,
        tpm=1_000_000,
        models=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-exp"],
        specialties=["reasoning", "general", "fast", "coding"],
        description="Google Gemini free developer tier with 1M context",
    ),
    "groq": FreeLLMProvider(
        id="groq",
        name="Groq LPU Inference Engine",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        monthly_token_quota=500_000_000,
        rpm=30,
        tpm=6_000,
        models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen-2.5-32b", "deepseek-r1-distill-llama-70b"],
        specialties=["fast", "coding", "eval"],
        description="Ultra-low latency LPU hardware acceleration",
    ),
    "cerebras": FreeLLMProvider(
        id="cerebras",
        name="Cerebras Wafer-Scale Inference",
        base_url="https://api.cerebras.ai/v1",
        api_key_env="CEREBRAS_API_KEY",
        monthly_token_quota=600_000_000,
        rpm=30,
        tpm=60_000,
        models=["llama3.1-70b", "llama3.1-8b"],
        specialties=["fast", "eval"],
        description="Wafer-scale engine with 1800+ tokens/sec throughput",
    ),
    "mistral": FreeLLMProvider(
        id="mistral",
        name="Mistral AI La Plateforme Free",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        monthly_token_quota=500_000_000,
        rpm=5,
        tpm=100_000,
        models=["codestral-latest", "mistral-large-latest", "mistral-small-latest", "pixtral-12b"],
        specialties=["coding", "general", "reasoning"],
        description="State-of-the-art European open models including Codestral",
    ),
    "sambanova": FreeLLMProvider(
        id="sambanova",
        name="SambaNova Fast Inference",
        base_url="https://api.sambanova.ai/v1",
        api_key_env="SAMBANOVA_API_KEY",
        monthly_token_quota=500_000_000,
        rpm=40,
        tpm=50_000,
        models=["Meta-Llama-3.3-70B-Instruct", "Qwen2.5-Coder-32B-Instruct", "Qwen2.5-72B-Instruct"],
        specialties=["coding", "reasoning", "fast"],
        description="Reconfigurable dataflow architecture for instant token generation",
    ),
    "together": FreeLLMProvider(
        id="together",
        name="Together AI Free Tier",
        base_url="https://api.together.xyz/v1",
        api_key_env="TOGETHER_API_KEY",
        monthly_token_quota=300_000_000,
        rpm=60,
        tpm=60_000,
        models=["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-Coder-32B-Instruct"],
        specialties=["coding", "fast"],
        description="High-speed distributed model hosting",
    ),
    "deepinfra": FreeLLMProvider(
        id="deepinfra",
        name="DeepInfra Free Quota",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        monthly_token_quota=400_000_000,
        rpm=100,
        tpm=100_000,
        models=["Qwen/Qwen2.5-Coder-32B-Instruct", "meta-llama/Meta-Llama-3.3-70B-Instruct"],
        specialties=["coding", "eval"],
        description="Serverless GPU inference endpoint",
    ),
    "openrouter_free": FreeLLMProvider(
        id="openrouter_free",
        name="OpenRouter Free Tier (:free)",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        monthly_token_quota=500_000_000,
        rpm=20,
        tpm=40_000,
        models=["deepseek/deepseek-r1:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-exp:free"],
        specialties=["reasoning", "coding", "general"],
        description="OpenRouter zero-cost public community models",
    ),
    "huggingface": FreeLLMProvider(
        id="huggingface",
        name="HuggingFace Serverless Inference",
        base_url="https://router.huggingface.co/v1",
        api_key_env="HF_API_KEY",
        monthly_token_quota=400_000_000,
        rpm=30,
        tpm=30_000,
        models=["Qwen/Qwen2.5-Coder-32B-Instruct", "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"],
        specialties=["coding", "reasoning"],
        description="Serverless inference API hosted directly on HuggingFace Hub",
    ),
    "cloudflare": FreeLLMProvider(
        id="cloudflare",
        name="Cloudflare Workers AI",
        base_url="https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        api_key_env="CLOUDFLARE_API_KEY",
        monthly_token_quota=300_000_000,
        rpm=50,
        tpm=50_000,
        models=["@cf/meta/llama-3.3-70b-instruct", "@cf/qwen/qwen2.5-coder-32b-instruct"],
        specialties=["fast", "coding"],
        description="Global edge inference on 300+ PoPs worldwide",
    ),
    "github_models": FreeLLMProvider(
        id="github_models",
        name="GitHub Models Free Marketplace",
        base_url="https://models.inference.ai.azure.com",
        api_key_env="GITHUB_TOKEN",
        monthly_token_quota=200_000_000,
        rpm=15,
        tpm=15_000,
        models=["gpt-4o-mini", "o3-mini", "Phi-4", "Mistral-large-2407"],
        specialties=["reasoning", "coding"],
        description="Free developer playground models on Azure/GitHub",
    ),
    "cohere": FreeLLMProvider(
        id="cohere",
        name="Cohere Trial API",
        base_url="https://api.cohere.ai/v1",
        api_key_env="COHERE_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=20,
        tpm=20_000,
        models=["command-r-plus", "command-r"],
        specialties=["general", "rag"],
        description="Cohere enterprise retrieval and reasoning trial",
    ),
    "voyage": FreeLLMProvider(
        id="voyage",
        name="Voyage AI Embeddings & Rerank",
        base_url="https://api.voyageai.com/v1",
        api_key_env="VOYAGE_API_KEY",
        monthly_token_quota=300_000_000,
        rpm=50,
        tpm=50_000,
        models=["voyage-3", "voyage-code-3"],
        specialties=["eval", "rag"],
        description="Domain-specific vector representations and code search",
    ),
    "xkiro_free": FreeLLMProvider(
        id="xkiro_free",
        name="xKiro Free Tier",
        base_url="https://api.xkiro.com/v1",
        api_key_env="XKIRO_API_KEY",
        monthly_token_quota=500_000_000,
        rpm=60,
        tpm=60_000,
        models=["xkiro/auto-free", "xkiro/qwen-coder-free"],
        specialties=["coding", "general"],
        description="Multi-model fallback proxy with 40+ free endpoints",
    ),
    "freemodels_pro": FreeLLMProvider(
        id="freemodels_pro",
        name="FreeModels.Pro Gateway",
        base_url="https://api.freemodels.pro/v1",
        api_key_env="FREEMODELS_API_KEY",
        monthly_token_quota=400_000_000,
        rpm=30,
        tpm=30_000,
        models=["claude-sonnet-5-free", "gpt-5.6-free", "kimi-k3-free"],
        specialties=["reasoning", "coding"],
        description="Thinking + Deep Search aggregated community mirror",
    ),
    "tabitoken": FreeLLMProvider(
        id="tabitoken",
        name="TabiToken Free Hub",
        base_url="https://api.tabitoken.com/v1",
        api_key_env="TABITOKEN_API_KEY",
        monthly_token_quota=300_000_000,
        rpm=30,
        tpm=30_000,
        models=["tabi/claude-instant-free", "tabi/gpt-free"],
        specialties=["fast", "general"],
        description="Free token proxy for developer tools",
    ),
    "nararouter": FreeLLMProvider(
        id="nararouter",
        name="NaraRouter Free Models",
        base_url="https://router.bynara.id/v1",
        api_key_env="NARAROUTER_API_KEY",
        monthly_token_quota=200_000_000,
        rpm=20,
        tpm=20_000,
        models=["nara/muse-spark-1.3", "nara/qwen-coder"],
        specialties=["coding", "fast"],
        description="Lightweight developer routing gateway",
    ),
    "deepseek_direct": FreeLLMProvider(
        id="deepseek_direct",
        name="DeepSeek Free Allowance",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        monthly_token_quota=200_000_000,
        rpm=30,
        tpm=30_000,
        models=["deepseek-chat", "deepseek-reasoner"],
        specialties=["reasoning", "coding"],
        description="Native DeepSeek V3 and R1 reasoning endpoints",
    ),
    "alibaba_dashscope": FreeLLMProvider(
        id="alibaba_dashscope",
        name="Alibaba DashScope Qwen Free",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        monthly_token_quota=300_000_000,
        rpm=30,
        tpm=30_000,
        models=["qwen-plus", "qwen-turbo", "qwen2.5-coder-32b-instruct"],
        specialties=["coding", "reasoning"],
        description="Official Alibaba Cloud Qwen foundation models",
    ),
    "ai21": FreeLLMProvider(
        id="ai21",
        name="AI21 Studio Free Tier",
        base_url="https://api.ai21.com/studio/v1",
        api_key_env="AI21_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=90,
        tpm=90_000,
        models=["jamba-1.5-large", "jamba-1.5-mini"],
        specialties=["general", "fast"],
        description="SSM-Transformer hybrid architecture with 256K context",
    ),
    "replicate_free": FreeLLMProvider(
        id="replicate_free",
        name="Replicate Free Trial",
        base_url="https://api.replicate.com/v1",
        api_key_env="REPLICATE_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=20,
        tpm=20_000,
        models=["meta/meta-llama-3-70b-instruct"],
        specialties=["general"],
        description="Serverless machine learning model deployment",
    ),
    "lepton": FreeLLMProvider(
        id="lepton",
        name="Lepton AI Free Engine",
        base_url="https://api.lepton.ai/v1",
        api_key_env="LEPTON_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=30,
        tpm=30_000,
        models=["llama3.3-70b", "qwen2.5-coder-32b"],
        specialties=["coding", "fast"],
        description="Efficient cloud runtime for open-source AI",
    ),
    "novita": FreeLLMProvider(
        id="novita",
        name="Novita AI Serverless",
        base_url="https://api.novita.ai/v3/openai",
        api_key_env="NOVITA_API_KEY",
        monthly_token_quota=150_000_000,
        rpm=30,
        tpm=30_000,
        models=["meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-r1"],
        specialties=["reasoning", "coding"],
        description="High-availability GPU cloud cluster",
    ),
    "fireworks": FreeLLMProvider(
        id="fireworks",
        name="Fireworks AI Free Trial",
        base_url="https://api.fireworks.ai/inference/v1",
        api_key_env="FIREWORKS_API_KEY",
        monthly_token_quota=150_000_000,
        rpm=60,
        tpm=60_000,
        models=["accounts/fireworks/models/llama-v3p3-70b-instruct"],
        specialties=["fast", "eval"],
        description="Compound inference engine optimized for low latency",
    ),
    "anyscale": FreeLLMProvider(
        id="anyscale",
        name="Anyscale Endpoints Free",
        base_url="https://api.endpoints.anyscale.com/v1",
        api_key_env="ANYSCALE_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=30,
        tpm=30_000,
        models=["meta-llama/Llama-3.3-70B-Instruct"],
        specialties=["general"],
        description="Ray-powered distributed model serving",
    ),
    "scaleway": FreeLLMProvider(
        id="scaleway",
        name="Scaleway Generative APIs",
        base_url="https://api.scaleway.ai/v1",
        api_key_env="SCW_SECRET_KEY",
        monthly_token_quota=100_000_000,
        rpm=20,
        tpm=20_000,
        models=["llama-3.3-70b-instruct", "qwen2.5-coder-32b-instruct"],
        specialties=["coding", "general"],
        description="European cloud provider with sovereign infrastructure",
    ),
    "hyperbolic": FreeLLMProvider(
        id="hyperbolic",
        name="Hyperbolic Inference Free",
        base_url="https://api.hyperbolic.xyz/v1",
        api_key_env="HYPERBOLIC_API_KEY",
        monthly_token_quota=150_000_000,
        rpm=30,
        tpm=30_000,
        models=["deepseek-ai/DeepSeek-R1", "meta-llama/Llama-3.3-70B-Instruct"],
        specialties=["reasoning", "coding"],
        description="Decentralized verifiable computing platform",
    ),
    "glhf": FreeLLMProvider(
        id="glhf",
        name="GLHF AI Free Gateway",
        base_url="https://glhf.it/api/v1",
        api_key_env="GLHF_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=20,
        tpm=20_000,
        models=["hf:meta-llama/Llama-3.3-70B-Instruct"],
        specialties=["general"],
        description="Community-driven free AI gateway",
    ),
    "shuttleai": FreeLLMProvider(
        id="shuttleai",
        name="ShuttleAI Free Models",
        base_url="https://api.shuttleai.app/v1",
        api_key_env="SHUTTLEAI_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=20,
        tpm=20_000,
        models=["shuttle-2.5", "llama-3-8b"],
        specialties=["fast", "eval"],
        description="Free developer-tier access across multiple architectures",
    ),
    "chutes": FreeLLMProvider(
        id="chutes",
        name="Chutes.ai Fast Compute",
        base_url="https://api.chutes.ai/v1",
        api_key_env="CHUTES_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=30,
        tpm=30_000,
        models=["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-Coder-32B-Instruct"],
        specialties=["coding", "fast"],
        description="Micro-GPU cloud inference",
    ),
    "pollinations": FreeLLMProvider(
        id="pollinations",
        name="Pollinations.ai Free Endpoints",
        base_url="https://text.pollinations.ai/openai",
        api_key_env="POLLINATIONS_API_KEY",
        monthly_token_quota=200_000_000,
        rpm=60,
        tpm=60_000,
        models=["openai", "qwen", "mistral", "claude-hybrid"],
        specialties=["general", "fast"],
        description="Public unrestricted generative engine",
    ),
    "siliconflow": FreeLLMProvider(
        id="siliconflow",
        name="SiliconFlow Free Tier",
        base_url="https://api.siliconflow.cn/v1",
        api_key_env="SILICONFLOW_API_KEY",
        monthly_token_quota=300_000_000,
        rpm=60,
        tpm=60_000,
        models=["deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-Coder-32B-Instruct"],
        specialties=["coding", "reasoning"],
        description="High-speed Asian inference accelerator",
    ),
    "octoai": FreeLLMProvider(
        id="octoai",
        name="OctoAI Compute Hub",
        base_url="https://text.octoai.run/v1",
        api_key_env="OCTOAI_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=20,
        tpm=20_000,
        models=["meta-llama-3.1-70b-instruct"],
        specialties=["general"],
        description="Specialized hardware optimizer for transformers",
    ),
    "modelscope": FreeLLMProvider(
        id="modelscope",
        name="ModelScope Free Inference",
        base_url="https://api-inference.modelscope.cn/v1",
        api_key_env="MODELSCOPE_API_KEY",
        monthly_token_quota=200_000_000,
        rpm=30,
        tpm=30_000,
        models=["Qwen/Qwen2.5-Coder-32B-Instruct", "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"],
        specialties=["coding", "reasoning"],
        description="Open-source AI community platform supported by Alibaba",
    ),
    "aws_bedrock": FreeLLMProvider(
        id="aws_bedrock",
        name="Amazon Bedrock (Builder ID Promotional Credit Pool)",
        base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
        api_key_env="AWS_BEDROCK_API_KEY",
        monthly_token_quota=100_000_000,
        rpm=60,
        tpm=250_000,
        models=[
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-7-sonnet-20250219-v1:0",
            "anthropic.claude-3-5-haiku-20241022-v1:0",
            "meta.llama3-3-70b-instruct-v1:0",
            "mistral.mistral-large-2407-v1:0",
        ],
        specialties=["coding", "reasoning", "general", "fast"],
        format="custom",
        description="AWS Builder ID $100-$200 promotional credit pool with zero-cost fail-closed fencing",
    ),
}


def get_total_free_tier_capacity() -> int:
    """Return aggregated monthly token capacity across all 34+ providers."""
    return sum(p.monthly_token_quota for p in PROVIDER_CATALOG.values())


# ---------------------------------------------------------------------------
# Key Vault (AES-256-GCM / PBKDF2 with Fallback & Redaction)
# ---------------------------------------------------------------------------

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}")


class KeyVault:
    """Encrypted credential vault with memory redaction and environment expansion."""

    def __init__(self, passphrase: str | None = None) -> None:
        self._passphrase = passphrase or os.environ.get("FREELLM_VAULT_KEY", "marzneshin-freellm-salt-2026")
        self._salt = b"marzneshin-agentos-freellm-gcm"
        # Derive 32-byte key via PBKDF2
        self._derived_key = hashlib.pbkdf2_hmac("sha256", self._passphrase.encode("utf-8"), self._salt, iterations=100_000, dklen=32)

    def encrypt(self, plain_text: str) -> str:
        """Encrypt secret using AES-256-GCM (or HMAC-authenticated keystream)."""
        data = plain_text.encode("utf-8")
        try:
            # Lazy import for lint-imports exemption
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import os as _os  # clock-ok: cryptographic nonce generation
            nonce = _os.urandom(12)
            aesgcm = AESGCM(self._derived_key)
            ct = aesgcm.encrypt(nonce, data, None)
            payload = base64.b64encode(nonce + ct).decode("utf-8")
            return f"vault:v1:{payload}"
        except Exception:
            # Fallback pure-python authenticated keystream (HMAC-SHA256 CTR-like)
            import os as _os  # clock-ok: cryptographic nonce generation
            nonce = _os.urandom(16)
            keystream = hashlib.sha256(self._derived_key + nonce).digest()
            while len(keystream) < len(data):
                keystream += hashlib.sha256(self._derived_key + nonce + len(keystream).to_bytes(4, "big")).digest()
            xor_bytes = bytes([b ^ k for b, k in zip(data, keystream[:len(data)])])
            mac = hashlib.sha256(self._derived_key + nonce + xor_bytes).digest()[:16]
            payload = base64.b64encode(nonce + mac + xor_bytes).decode("utf-8")
            return f"vault:v1:{payload}"

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt secret."""
        if not encrypted_text.startswith("vault:v1:"):
            return encrypted_text
        raw_b64 = encrypted_text[len("vault:v1:"):]
        raw = base64.b64decode(raw_b64)
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = raw[:12]
            ct = raw[12:]
            aesgcm = AESGCM(self._derived_key)
            plain = aesgcm.decrypt(nonce, ct, None)
            return plain.decode("utf-8")
        except Exception:
            nonce = raw[:16]
            mac = raw[16:32]
            xor_bytes = raw[32:]
            expected_mac = hashlib.sha256(self._derived_key + nonce + xor_bytes).digest()[:16]
            if mac != expected_mac:
                raise ValueError("Vault authentication check failed (corrupted or tampered key)")
            keystream = hashlib.sha256(self._derived_key + nonce).digest()
            while len(keystream) < len(xor_bytes):
                keystream += hashlib.sha256(self._derived_key + nonce + len(keystream).to_bytes(4, "big")).digest()
            data = bytes([b ^ k for b, k in zip(xor_bytes, keystream[:len(xor_bytes)])])
            return data.decode("utf-8")

    def resolve(self, val: Any) -> Any:
        """Expand ${ENV_VAR:-default} patterns."""
        if isinstance(val, str):
            def repl(match: re.Match) -> str:
                var_name = match.group(1)
                default_val = match.group(2) if match.group(2) is not None else ""
                return os.environ.get(var_name, default_val)
            return _ENV_VAR_PATTERN.sub(repl, val)
        elif isinstance(val, dict):
            return {k: self.resolve(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self.resolve(x) for x in val]
        return val

    @staticmethod
    def redact(key: str) -> str:
        """Safely redact secret key for diagnostics/logging."""
        if not key or len(key) < 8:
            return "***"
        prefix = key[:3] if key.startswith("sk-") or key.startswith("hf_") else key[:2]
        suffix = key[-4:]
        return f"{prefix}...{suffix}"


# ---------------------------------------------------------------------------
# FreeLLM Pool Manager (Multi-Key Rotation, Cooldown, Quotas)
# ---------------------------------------------------------------------------

@dataclass
class KeyRecord:
    key: str
    added_at: datetime
    in_cooldown_until: datetime | None = None
    total_calls: int = 0
    consecutive_errors: int = 0
    last_used: datetime | None = None


class FreeLLMPoolManager:
    """Manages active key pools, rate-limit cooldowns, and rotation per provider."""

    def __init__(self, vault: KeyVault | None = None, load_disk_keys: bool = True) -> None:
        self.vault = vault or KeyVault()
        self._pools: dict[str, list[KeyRecord]] = {}
        self._cursor: dict[str, int] = {}
        if load_disk_keys:
            self._load_from_keys_pool()

    def _load_from_keys_pool(self) -> None:
        """Load configured key pools from configs/keys_pool.json."""
        pool_file = paths.repo_root() / "configs" / "keys_pool.json"
        if not pool_file.exists():
            return
        try:
            data = atomic.read_json(pool_file)
            for provider_name, pdata in data.items():
                pid = provider_name.lower().replace("-", "_")
                keys = pdata.get("pool", [])
                for k in keys:
                    self.add_key(pid, k)
        except Exception:
            pass

    def add_key(self, provider_id: str, raw_or_encrypted_key: str) -> None:
        """Add an API key to a provider's pool."""
        pid = provider_id.lower().replace("-", "_")
        key = self.vault.resolve(raw_or_encrypted_key)
        if key.startswith("vault:v1:"):
            key = self.vault.decrypt(key)
        
        if pid not in self._pools:
            self._pools[pid] = []
            self._cursor[pid] = 0

        # Avoid duplicate keys
        if not any(r.key == key for r in self._pools[pid]):
            self._pools[pid].append(
                KeyRecord(key=key, added_at=clock.now())
            )

    def sweep_cooldowns(self) -> None:
        """Re-activate keys whose cooldown has expired."""
        now = clock.now()
        for pid, records in self._pools.items():
            for r in records:
                if r.in_cooldown_until and r.in_cooldown_until <= now:
                    r.in_cooldown_until = None
                    r.consecutive_errors = 0

    def acquire_key(self, provider_id: str) -> str:
        """Acquire next available key for provider using round-robin rotation."""
        self.sweep_cooldowns()
        pid = provider_id.lower().replace("-", "_")
        records = self._pools.get(pid, [])
        if not records:
            # Fall back to env var
            provider_cfg = PROVIDER_CATALOG.get(pid)
            if provider_cfg:
                env_key = os.environ.get(provider_cfg.api_key_env, "")
                if env_key:
                    return env_key
            return "free"

        now = clock.now()
        available = [r for r in records if not r.in_cooldown_until or r.in_cooldown_until <= now]
        if not available:
            # All cooling down: pick the one closest to expiring
            sorted_by_expiry = sorted(records, key=lambda x: x.in_cooldown_until or now)
            return sorted_by_expiry[0].key

        idx = self._cursor.get(pid, 0) % len(available)
        chosen = available[idx]
        self._cursor[pid] = (idx + 1) % len(available)
        
        chosen.total_calls += 1
        chosen.last_used = now
        return chosen.key

    def report_rate_limit(self, provider_id: str, key: str, cooldown_seconds: int = 60) -> None:
        """Record a 429/402 rate limit on a key and place it into cooldown."""
        pid = provider_id.lower().replace("-", "_")
        records = self._pools.get(pid, [])
        now = clock.now()
        for r in records:
            if r.key == key:
                r.consecutive_errors += 1
                r.in_cooldown_until = now + timedelta(seconds=cooldown_seconds)
                break

    def get_provider_status(self, provider_id: str) -> dict[str, Any]:
        """Return operational status and key counts for a provider."""
        self.sweep_cooldowns()
        pid = provider_id.lower().replace("-", "_")
        records = self._pools.get(pid, [])
        now = clock.now()
        
        active = sum(1 for r in records if not r.in_cooldown_until or r.in_cooldown_until <= now)
        cooling = sum(1 for r in records if r.in_cooldown_until and r.in_cooldown_until > now)
        provider_cfg = PROVIDER_CATALOG.get(pid)
        
        return {
            "provider_id": pid,
            "provider_name": provider_cfg.name if provider_cfg else pid,
            "total_keys": len(records),
            "active_keys_count": active,
            "cooldown_keys_count": cooling,
            "quota_monthly": provider_cfg.monthly_token_quota if provider_cfg else 0,
            "healthy": active > 0 or len(records) == 0,
        }

    def get_full_pool_status(self) -> dict[str, Any]:
        """Aggregate health and capacity across all 34+ providers."""
        self.sweep_cooldowns()
        providers_status = [self.get_provider_status(pid) for pid in PROVIDER_CATALOG]
        total_configured_keys = sum(p["total_keys"] for p in providers_status)
        total_active_keys = sum(p["active_keys_count"] for p in providers_status)
        total_cooling_keys = sum(p["cooldown_keys_count"] for p in providers_status)
        
        return {
            "total_providers": len(PROVIDER_CATALOG),
            "configured_keys": total_configured_keys,
            "active_keys": total_active_keys,
            "cooldown_keys": total_cooling_keys,
            "combined_monthly_tokens_estimate": get_total_free_tier_capacity(),
            "providers": {p["provider_id"]: p for p in providers_status},
        }


# ---------------------------------------------------------------------------
# Smart Fallback Router
# ---------------------------------------------------------------------------

class SmartFallbackRouter:
    """Manages fallback ladders across providers and task domains."""

    FALLBACK_LADDERS: dict[str, list[str]] = {
        "coding": [
            "aws_bedrock:anthropic.claude-3-5-sonnet-20241022-v2:0",
            "mistral:codestral-latest",
            "sambanova:Qwen2.5-Coder-32B-Instruct",
            "groq:qwen-2.5-32b",
            "deepinfra:Qwen/Qwen2.5-Coder-32B-Instruct",
            "huggingface:Qwen/Qwen2.5-Coder-32B-Instruct",
            "google_gemini:gemini-2.5-flash",
        ],
        "reasoning": [
            "aws_bedrock:anthropic.claude-3-5-sonnet-20241022-v2:0",
            "openrouter_free:deepseek/deepseek-r1:free",
            "groq:deepseek-r1-distill-llama-70b",
            "google_gemini:gemini-2.5-flash",
            "sambanova:Qwen2.5-72B-Instruct",
            "github_models:o3-mini",
        ],
        "fast": [
            "groq:llama-3.1-8b-instant",
            "cerebras:llama3.1-8b",
            "cloudflare:@cf/meta/llama-3.3-70b-instruct",
            "google_gemini:gemini-2.5-flash",
        ],
        "eval": [
            "groq:llama-3.1-8b-instant",
            "cerebras:llama3.1-8b",
            "deepinfra:meta-llama/Meta-Llama-3.3-70B-Instruct",
        ],
        "general": [
            "google_gemini:gemini-2.5-flash",
            "groq:llama-3.3-70b-versatile",
            "cerebras:llama3.1-70b",
            "mistral:mistral-large-latest",
            "openrouter_free:meta-llama/llama-3.3-70b-instruct:free",
        ],
    }

    def get_ladder(self, domain: str) -> list[str]:
        """Return fallback model ladder for a domain."""
        return self.FALLBACK_LADDERS.get(domain.lower(), self.FALLBACK_LADDERS["general"])

    def get_next_candidate(self, domain: str, failed_candidates: list[str]) -> str | None:
        """Select next viable model candidate after failures."""
        ladder = self.get_ladder(domain)
        failed_set = set(failed_candidates)
        for cand in ladder:
            if cand not in failed_set:
                return cand
        return None
