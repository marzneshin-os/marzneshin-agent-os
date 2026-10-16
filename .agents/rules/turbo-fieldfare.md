# TurboFieldfare Model Steering Rule (Gemma 4 26B-A4B SSD Streaming)

This rule guides autonomous agents when utilizing the **TurboFieldfare** (`gemma-4-26b-a4b-it`) local runtime.

## Core Capabilities
- **Model**: Instruction-tuned Gemma 4 26B-A4B (26B total parameters, ~3.88B active per token).
- **RAM Footprint**: Strictly constrained to ~2.0 GB of working RAM (1.35 GB resident common weights + 305 MB FP16 KV cache + scratch).
- **SSD Streaming**: 128 routed experts per layer across 30 layers streamed from SSD on demand via `pread` into a 16-slot per-layer LFU cache.
- **Cost**: $0.00 / 100% Free, local airgap execution with zero cloud dependency.
- **Throughput**: 5.1-6.3 tok/s on M2 MacBook Air (8GB RAM), 31-35 tok/s on M5 Pro (24GB RAM).

## When to Select TurboFieldfare
1. **Low Memory Workstations**: When the host machine has <= 8 GB of RAM or strict memory constraints where traditional 16GB+ models trigger out-of-memory kernel panics.
2. **Local Airgap & High Privacy**: When processing sensitive code, credentials, or proprietary documents that must never leave the local environment.
3. **Zero-Spend Long-Running Loops**: When running continuous agent loops or background autonomous tasks without incurring API token billing.
4. **Offline Operations**: When network connectivity is intermittent or disconnected.

## Operational Directives
1. **Loopback Server**: The runtime exposes an OpenAI-compatible server at `http://127.0.0.1:8080/v1` (`POST /v1/chat/completions`).
2. **Fail-Closed Fallback**: If the local `TurboFieldfareServer` process is stopped or inaccessible, the adapter cleanly falls back without crashing the agent pipeline.
3. **Single Model Process**: Never run concurrent model processes that claim the `.gturbo` model directory simultaneously.
