"""Adapter for OmniRoute / Claude Code Router (CCR) LLM Gateway.

Translates internal `llm_chat` ops to OpenAI-compatible HTTP requests.
Supports both OmniRoute (port 8080/3000) and CCR (port 3456) gateways,
with automatic fallback and combo resolution.
Implements the standard L0 Adapter protocol (§4).
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any

from adapters.base import (
    Adapter,
    AdapterRefused,
    CircuitBreaker,
    Health,
    IdemClass,
    IdempotencyStore,
    Result,
    deadline_remaining_s,
)

from scripts.lib import router, tokensaver


def _build_url(base_url: str, path: str) -> str:
    """Safely build URL avoiding double /v1/v1/ segments."""
    base = base_url.rstrip("/")
    p = path.lstrip("/")
    if base.endswith("/v1") and p.startswith("v1/"):
        p = p[3:].lstrip("/")
    return f"{base}/{p}"


class OmniRouteAdapter(Adapter):
    name = "omniroute"

    def __init__(self, world: str = "prod", gateway_name: str | None = None):
        self.world = world
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()
        self.gateway_name = gateway_name

    def _resolve_gateway(self, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Resolve target gateway name and config."""
        gateways = config.get("gateways", {})
        
        # 1. Explicitly requested gateway
        if self.gateway_name and self.gateway_name in gateways:
            return self.gateway_name, gateways[self.gateway_name]
        
        # 2. Prefer CCR if configured and enabled
        if config.get("routing", {}).get("prefer_ccr", False) and "ccr" in gateways:
            ccr_gw = gateways["ccr"]
            if ccr_gw.get("enabled", True):
                return "ccr", ccr_gw
                
        # 3. Fallback to adapter's default name
        if self.name in gateways:
            return self.name, gateways[self.name]
            
        # 4. Fallback to first enabled gateway
        for gw_name, gw_cfg in gateways.items():
            if gw_cfg.get("enabled", True):
                return gw_name, gw_cfg
                
        return self.name, {}

    def healthz(self) -> Health:
        try:
            config = router.load_config()
            gw_name, gw = self._resolve_gateway(config)
            base_url = gw.get("base_url", "http://localhost:3000")
            api_key = gw.get("api_key", "")
            
            url = _build_url(base_url, "v1/models")
            req = urllib.request.Request(url)
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("User-Agent", "Marzneshin-AgentOS/0.9")
            
            import time
            start = time.monotonic()
            with urllib.request.urlopen(req, timeout=3.0) as response:
                body = response.read()
                data = json.loads(body.decode("utf-8"))
                models_count = len(data.get("data", []))
            latency = (time.monotonic() - start) * 1000
            return Health(
                ok=True,
                detail=f"Gateway '{gw_name}' reachable ({models_count} models)",
                latency_ms=latency
            )
        except Exception as e:
            return Health(ok=False, detail=str(e), latency_ms=0.0)

    def capabilities(self) -> list[str]:
        return ["llm_chat", "llm_reason", "llm_think", "llm_search"]

    def execute(
        self,
        op: str,
        payload: dict,
        *,
        idem_key: str,
        idem_class: IdemClass,
        dry_run: bool,
        deadline: datetime,
        provenance: list[dict]
    ) -> Result:
        if op not in self.capabilities():
            return Result(ok=False, op=op, error=f"unknown op: {op}")

        # Inject capability flags into payload based on op
        if op == "llm_reason":
            payload.setdefault("reasoning_effort", "high")
        elif op == "llm_think":
            payload.setdefault("thinking", True)
        elif op == "llm_search":
            payload.setdefault("deep_search", True)

        stored = self._idem.lookup(idem_key)
        if stored:
            return stored

        if dry_run:
            res = Result(
                ok=True,
                op=op,
                dry_run=True,
                data={"choices": [{"message": {"content": "dry_run"}}]}
            )
            self._idem.save(idem_key, res, klass=idem_class)
            return res

        self._circuit.before_call()

        try:
            res = self._execute_chat(payload, deadline, op=op)
            self._circuit.on_success()
            self._idem.save(idem_key, res, klass=idem_class)
            return res
        except AdapterRefused as e:
            return Result(ok=False, op=op, error=str(e))
        except Exception as e:
            self._circuit.on_failure()
            return Result(ok=False, op=op, error=str(e))

    def _execute_chat(self, payload: dict, deadline: datetime, op: str = "llm_chat") -> Result:
        import time
        
        config = router.load_config()
        model = payload.get("model", "auto")
        
        # Check if model is a combo name
        combo_cfg = router.get_combo_strategy(model)
        candidates = combo_cfg.members if combo_cfg else [model]
        is_combo = combo_cfg is not None

        # Prioritize candidates if specific reasoning/thinking/search capabilities are requested
        want_thinking = bool(payload.get("thinking") or payload.get("thinking_mode") or op == "llm_think")
        want_deep_search = bool(payload.get("deep_search") or op == "llm_search")
        want_reasoning = bool(payload.get("reasoning_effort") or payload.get("reasoning") or op == "llm_reason")

        if is_combo and (want_thinking or want_deep_search or want_reasoning):
            def _score_candidate(cand: str) -> int:
                c = cand.lower()
                score = 0
                if want_thinking and ("think" in c or "fable" in c or "freemodels" in c or "sonnet" in c):
                    score += 10
                if want_deep_search and ("freemodels" in c or "search" in c or "fable" in c):
                    score += 10
                if want_reasoning and ("reason" in c or "deepseek" in c or "glm" in c or "qwen" in c or "sol" in c or "terra" in c):
                    score += 5
                return score
            candidates = sorted(candidates, key=_score_candidate, reverse=True)

        last_err = None
        for candidate_model in candidates:
            # Determine target gateway for candidate
            target_gw_name = None
            raw_model = candidate_model
            
            if candidate_model.startswith("ccr:"):
                target_gw_name = "ccr"
                raw_model = candidate_model[4:]
            elif ":" in candidate_model:
                parts = candidate_model.split(":", 1)
                prefix = parts[0].lower()
                if prefix in config.get("gateways", {}):
                    target_gw_name = prefix
                    raw_model = parts[1]

            if not target_gw_name:
                gw_name, gw_cfg = self._resolve_gateway(config)
            else:
                gw_name = target_gw_name
                gw_cfg = config.get("gateways", {}).get(gw_name, {})

            if not gw_cfg.get("enabled", True):
                continue

            base_url = gw_cfg.get("base_url", "http://localhost:3000")
            api_key = gw_cfg.get("api_key", "sk-local")

            body: dict[str, Any] = {
                "model": raw_model,
                "messages": payload.get("messages", [])
            }

            # Pass through standard hyperparameters
            for key in ("temperature", "max_tokens", "top_p", "stream", "tools", "tool_choice", "response_format"):
                if key in payload and payload[key] is not None:
                    body[key] = payload[key]

            # Reasoning Effort (OpenAI o-series, xKiro, CCR)
            reasoning_effort = payload.get("reasoning_effort") or payload.get("reasoning")
            if reasoning_effort:
                if isinstance(reasoning_effort, str):
                    body["reasoning_effort"] = reasoning_effort
                elif isinstance(reasoning_effort, dict):
                    body["reasoning"] = reasoning_effort

            # Thinking Mode (FreeModels, Anthropic, Qwen, DeepSeek)
            if payload.get("thinking") is not None:
                body["thinking"] = payload["thinking"]
            elif payload.get("thinking_mode"):
                body["thinking"] = True

            # Deep Search (FreeModels.Pro, Perplexity, etc.)
            if payload.get("deep_search") is not None:
                body["deep_search"] = payload["deep_search"]
            elif payload.get("search"):
                body["deep_search"] = True
            
            rtk_enabled = payload.get("rtk_enabled", True)
            caveman = payload.get("caveman_level")
            ponytail = payload.get("ponytail_enabled", False)
            
            metrics = tokensaver.apply_token_saver(
                body,
                rtk_enabled=rtk_enabled,
                caveman_level=caveman,
                ponytail_enabled=ponytail
            )

            timeout = deadline_remaining_s(deadline)
            if timeout <= 0:
                raise AdapterRefused("Deadline exceeded before request started")

            url = _build_url(base_url, "v1/chat/completions")
            req_body = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(url, data=req_body, method="POST")
            req.add_header("Content-Type", "application/json")
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("User-Agent", "Marzneshin-AgentOS/0.9")

            start = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    duration = (time.monotonic() - start) * 1000
                    
                    usage = resp_data.get("usage", {})
                    tokens_in = usage.get("prompt_tokens", 0)
                    tokens_out = usage.get("completion_tokens", 0)
                    total_tokens = tokens_in + tokens_out
                    
                    if total_tokens > 0:
                        router.record_usage(candidate_model, is_combo, total_tokens, metrics)
                        
                    return Result(
                        ok=True,
                        op=op,
                        data=resp_data,
                        duration_ms=duration
                    )
            except urllib.error.HTTPError as e:
                duration = (time.monotonic() - start) * 1000
                err_text = e.read().decode("utf-8")
                err_class = router.classify_error(e.code, err_text)
                last_err = f"HTTP {e.code} ({err_class}): {err_text}"
                if not is_combo and err_class in ("quota_exhausted", "auth_failed"):
                    raise AdapterRefused(f"{err_class}: {err_text}")
                # If in combo, continue to next candidate
                continue
            except Exception as e:
                last_err = f"Network error: {str(e)}"
                continue

        if last_err:
            raise Exception(f"All candidates failed for '{model}'. Last error: {last_err}")
        raise AdapterRefused(f"No enabled providers found for '{model}'")

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"ref": receipt_ref})


class CCRAdapter(OmniRouteAdapter):
    """Specialized adapter specifically addressing Claude Code Router."""
    name = "ccr"

    def __init__(self, world: str = "prod"):
        super().__init__(world=world, gateway_name="ccr")
