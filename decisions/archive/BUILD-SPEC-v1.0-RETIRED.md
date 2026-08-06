# BUILD-SPEC v1.0 — Marzneshin Autonomous OS (Implementation Brief for Claude Opus 5)

# BUILD-SPEC v1.0 — Marzneshin Autonomous OS
## Implementation Brief for Claude Opus 5
> **ورودی مرجع:** MASTER-PLAN v4.0 FINAL · **این سند:** قرارداد اجرایی (executable contract) برای مدلی که پیاده‌سازی می‌کند.  
> **قاعدهٔ کلی:** هرچه در MASTER-PLAN «چه چیزی» است، در این سند «دقیقاً چگونه» است. در تعارض، این سند حاکم است.
* * *
# ۰) قرارداد با مدل پیاده‌ساز (بخوان، بعد شروع کن)
**تو Owner فنی این پروژه‌ای، نه دستیار.** بدون پرسیدن سؤال‌های بدیهی شروع کن. جایی که سند ساکت است، تصمیم بگیر، تصمیم را در `decisions/ADR/` ثبت کن و ادامه بده.

**پروتکل پاسخ در هر جلسه (اجباری):**

```plain
1. SYNC        → state/STATE.json + HANDOFF.md + receipts اخیر را بخوان
2. GAP SCAN    → فاصلهٔ وضعیت فعلی تا Definition of Done اسلایس جاری
3. CLAIM       → lease بگیر (workstream-level، TTL 90m)
4. PLAN        → حداکثر ۷ گام، هر گام با artifact مشخص
5. EXECUTE     → کد/کانفیگ واقعی، نه شبه‌کد، نه TODO
6. VERIFY      → تست اجرا شود، خروجی واقعی گزارش شود
7. EMIT        → event + receipt + commit atomic
8. HANDOFF     → HANDOFF.md بازنویسی شود، lease آزاد شود
```

**ممنوعیت‌های مطلق برای مدل پیاده‌ساز:**
*   تحویل فایل خالی، `pass`، `TODO`, یا mock به‌جای پیاده‌سازی واقعی.
*   ادعای «تست پاس شد» بدون خروجی واقعی تست.
*   ساخت بیش از یک اسلایس هم‌زمان.
*   نوشتن secret در repo/prompt/log/artifact.
*   تغییر فایل خارج از `owns` اسلایس جاری بدون ADR.

**تعریف موفقیت نهایی:** یک سیستم که ۷۲ ساعت بدون مداخلهٔ انسانی کار کند، خودش تشخیص دهد، تصمیم بگیرد، اجرا کند، تأیید کند، در صورت خطا rollback کند و همهٔ اینها را با evidence قابل‌ممیزی ثبت کند.

* * *
# ۱) دامنه، خارج از دامنه، و اصول ثابت
## ۱.۱) In scope
Control Plane (Orchestrator + A2A Gateway + Policy Engine) · State Plane (GitHub SSoT + Events + Receipts) · Execution Layer (Claude Code + Hooks + Skills + MCP) · Control Room (ClickUp) · Growth/Revenue/Experiment Engine · Observability + Security + Governance.
## ۱.۲) Out of scope (صریحاً نساز)
UI اختصاصی داشبورد (از ClickUp Dashboard + Grafana استفاده کن) · CRM اختصاصی · Data warehouse سفارشی در فاز ۰-۳ (DuckDB/Postgres کافی است) · هر microservice که با یک module قابل انجام است.
## ۱.۳) Invariants (نقض = build شکست‌خورده)

| # | Invariant | مکانیزم اجبار |
| ---| ---| --- |
| I1 | GitHub تنها منبع حقیقت | ClickUp فقط mirror؛ نوشتن معکوس ممنوع جز approval flag |
| I2 | هر worker بی‌حالت است | SessionStart hook اجباری SYNC می‌کند |
| I3 | هیچ کار بدون receipt | TaskCompleted hook بدون receipt exit 1 |
| I4 | هیچ release بدون canary | release workflow بدون canary gate fail |
| I5 | هیچ کمپین بدون stop condition | campaign adapter schema validation |
| I6 | هیچ secret خام | gitleaks + PreToolUse redaction |
| I7 | هر تصمیم reversible | rollback plan فیلد اجباری در receipt |
| I8 | trade-off ثبت‌شده، نه صفر | `decisions/TRADEOFF-REGISTER.md` |
| I9 | هیچ ادعای بازاریابی بدون evidence | Trust Agent gate روی هر content artifact |
| I10 | blast radius محدود | policy engine + autonomy level |

* * *
# ۲) معماری هدف و ساختار مخزن
## ۲.۱) لایه‌ها

```plain
L5  Governance     Owner + ClickUp Approvals + Kill Switch
L4  Orchestration  Orchestrator Agent + Scheduler + Lease Manager
L3  Protocol       A2A Gateway + Agent Registry + Policy Engine + Audit Log
L2  Execution      Claude Code · Skills · Hooks · MCP · Subagents
L1  State          GitHub (SSoT) · Event Log · Receipts · Artifacts
L0  Systems        Marzneshin/Marznode · Payments · Analytics · Observability
```

قانون: هر لایه فقط با لایهٔ مجاور صحبت می‌کند. L2 هرگز مستقیم به L0 دست نمی‌زند، همیشه از Adapter در L1 عبور می‌کند.
## ۲.۲) ساختار مخزن (بساز دقیقاً همین)

```plain
marzneshin-ops/
├─ CLAUDE.md                      # قوانین پایدار، < 400 خط
├─ CONTEXT-PACK.md                # وضعیت فشرده برای شروع جلسه
├─ MASTER-PLAN.md                 # سند استراتژی (read-only)
├─ BUILD-SPEC.md                  # همین سند
├─ state/
│  ├─ STATE.json                  # snapshot compact شده
│  ├─ HANDOFF.md                  # آخرین وضعیت انسانی‌خوان
│  ├─ events/YYYY-MM-DD.ndjson    # append-only
│  ├─ locks/{workstream}.lock.json
│  └─ archive/
├─ receipts/YYYY/MM/T-xxxx.json
├─ decisions/ADR/ADR-xxx.md + TRADEOFF-REGISTER.md
├─ agents/{cards,policies,prompts}/
├─ skills/{fsp-session,growth-lifecycle,revenue-dashboard,experiment-loop,
│          campaign-launch,qa-gate,security-review,github-atomic-commit,handoff}/SKILL.md
├─ hooks/{session_start,pre_tool,post_tool,pre_commit,task_complete,stop}.py
├─ plugins/marzneshin-ops/
├─ gateway/                       # A2A Gateway (FastAPI)
│  ├─ app.py routes/ policy/ registry/ auth/ store/ tests/
├─ adapters/{github,clickup,marzneshin,payments,analytics,messaging,observability,vault}/
├─ mcp/{github,clickup,product,analytics,observability}.json
├─ growth/{personas,journeys,campaigns,offers,content,experiments}/
├─ analytics/{events,schemas,models,dashboards}/
├─ configs/{templates,profiles,releases}/
├─ infra/{terraform,ansible,compose}/
├─ scripts/{fsp.py,compact.py,context_pack.py,verify.py,experiment_guard.py,
│           succession.py,killswitch.py}
└─ .github/workflows/{validate,compact,release,mirror,security,notify,
                      experiment,heartbeat,succession}.yml
```

* * *
# ۳) قراردادهای داده (Canonical Schemas)
همهٔ اینها را در `analytics/schemas/` به‌صورت JSON Schema Draft 2020-12 بنویس و در CI اعتبارسنجی کن.
## ۳.۱) STATE.json

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-07-27T12:00:00Z",
  "compacted_from_event": 18422,
  "phase": "P1-agentic-core",
  "active_slice": "VS-2",
  "workstreams": {
    "agentic-core": {
      "owner_agent": "orchestrator",
      "lease": {"holder": "agent:config-eng", "expires_at": "...", "heartbeat_at": "..."},
      "open_tasks": ["T-0142"],
      "blocked_by": [],
      "last_receipt": "receipts/2026/07/T-0141.json",
      "health": "green"
    }
  },
  "kpis": {"connection_success_rate": 0.987, "activation_rate": 0.41, "nsm": 1284},
  "kill_switch": {"global": false, "scoped": []},
  "open_risks": [{"id": "R-07", "severity": "med", "owner": "sre"}]
}
```

## ۳.۲) Event (append-only، NDJSON)

```json
{"event_id":"ULID","seq":18423,"ts":"ISO8601","type":"task.completed",
 "actor":{"kind":"agent","id":"qa-agent","session":"S-91"},
 "subject":{"kind":"task","id":"T-0142"},
 "correlation_id":"C-...","causation_id":"E-...",
 "payload":{},"inputs_hash":"sha256:...","schema_version":"1.0.0","redacted":false}
```

قواعد: هرگز edit/delete. compact فقط snapshot جدید می‌سازد. `seq` یکنواخت صعودی با CAS روی فایل روز.
## ۳.۳) Receipt (بدون این، کار Done نیست)

```json
{
  "task_id": "T-0142",
  "agent": "config-engineer",
  "autonomy_level": "L2",
  "started_at": "...", "completed_at": "...",
  "intent": "انتشار profile reality-v7 روی canary 1%",
  "inputs_hash": "sha256:...",
  "changes": [{"path":"configs/profiles/reality-v7.yaml","commit":"abc123","diff_stat":"+42-3"}],
  "verification": [{"check":"qa-gate","result":"pass","evidence":"artifacts/qa/T-0142.json"},
                    {"check":"canary-probe","result":"pass","evidence":"...","metric":{"csr":0.991}}],
  "policy_decisions": [{"rule":"cfg.publish.canary","decision":"allow","reason":"..."}],
  "cost": {"tokens": 41200, "usd": 0.62, "wall_clock_s": 380},
  "rollback": {"method":"git revert abc123 + profile pin v6","tested":true,"tested_at":"..."},
  "handoff_note": "...",
  "clickup_task": "https://app.clickup.com/t/..."
}
```

## ۳.۴) Agent Card

```yaml
id: lifecycle-growth
name: Lifecycle Growth Agent
version: 1.2.0
tier: 2
owns: [growth/journeys/**, growth/campaigns/**]
capabilities: [journey.design, campaign.draft, campaign.launch, suppression.manage]
inputs: [analytics.funnel, product.usage, support.tickets]
outputs: [campaign.artifact, journey.spec, lifecycle.report]
autonomy: {default: L2, campaign.launch: L1, suppression.manage: L3}
budget: {tokens_per_day: 300000, usd_per_day: 8, campaign_spend_cap_usd: 200}
kpi: [activation_rate, trial_to_paid, nrr, unsubscribe_rate]
forbidden: [pricing_change, refund_issue, raw_pii_access, ad_spend_above_cap]
escalation: {to: orchestrator, on: [guardrail_breach, budget_80pct, policy_deny]}
dependencies: [content-creative, cro-experiment, revenue-intelligence]
heartbeat_sla_min: 15
```

## ۳.۵) A2A Task Envelope

```json
{"task_id":"A2A-...","idempotency_key":"sha256(from|to|capability|inputs_hash)",
 "from":"orchestrator","to":"qa-agent","capability":"qa.gate.run",
 "input":{"$schema":"...","artifact":"configs/profiles/reality-v7.yaml"},
 "deadline":"2026-07-27T13:00:00Z","priority":"high",
 "correlation_id":"C-...","callback":"https://gw/v1/tasks/{id}/events",
 "autonomy_requested":"L2","budget":{"tokens":50000},"trace_id":"..."}
```

## ۳.۶) Lease

```json
{"workstream":"agentic-core","holder":"agent:config-eng","session":"S-91",
 "acquired_at":"...","ttl_min":90,"heartbeat_at":"...","fencing_token":42}
```

قانون fencing: هر write به state باید `fencing_token >= current`، وگرنه reject. این تنها محافظ واقعی در برابر split-brain است.

* * *
# ۴) Ports & Adapters (قفل نشدن به vendor)
هر Adapter این interface را پیاده کند (Python Protocol / TS interface):

```python
class Adapter(Protocol):
    name: str
    def healthz(self) -> Health: ...
    def capabilities(self) -> list[str]: ...
    def execute(self, op: str, payload: dict, *, idem_key: str, dry_run: bool) -> Result: ...
    def rollback(self, receipt_ref: str) -> Result: ...
```

الزامات مشترک همهٔ Adapterها: idempotency، exponential backoff با jitter، circuit breaker (۵ خطای پیاپی → open برای ۶۰ ثانیه)، timeout سخت، redaction روی log، `dry_run` واقعی، و contract test مستقل.

| Adapter | Ops حداقلی |
| ---| --- |
| github | commit\_atomic, read\_state, append\_event, create\_pr, dispatch\_workflow |
| clickup | upsert\_task, comment, set\_status, set\_custom\_field, read\_approval |
| marzneshin | list\_nodes, publish\_config, probe, rollback\_profile, user\_provision |
| payments | create\_checkout, verify\_webhook, reconcile, refund (L1 only) |
| analytics | ingest\_event, query\_metric, cohort, experiment\_readout |
| messaging | send\_campaign, suppression\_add, quiet\_hours\_check |
| observability | push\_metric, query\_slo, fire\_alert, error\_budget |
| vault | get\_secret (short-lived), rotate, audit |

* * *
# ۵) A2A Gateway — مشخصات دقیق
**Stack:** FastAPI + Pydantic v2 + Postgres (tasks/audit) + Redis (rate limit, idempotency cache) + mTLS یا OIDC.
## ۵.۱) Endpoints

| Method | Path | رفتار |
| ---| ---| --- |
| GET | `/.well-known/agent-card.json` | کارت ایجنت میزبان |
| GET | `/healthz` `/readyz` | liveness/readiness |
| GET | `/v1/agents` | Registry، فیلتر بر capability |
| POST | `/v1/tasks` | ایجاد task، `202` + `task_id`؛ idempotent |
| GET | `/v1/tasks/{id}` | وضعیت + آخرین state |
| POST | `/v1/tasks/{id}/messages` | پیام میان‌مرحله‌ای |
| POST | `/v1/tasks/{id}/cancel` | لغو با دلیل، rollback خودکار در صورت نیاز |
| GET | `/v1/tasks/{id}/events` | SSE stream |
| POST/GET | `/v1/artifacts[/{id}]` | آپلود/دریافت artifact با hash |
| POST | `/v1/policy/evaluate` | dry-run تصمیم policy |
| POST | `/v1/killswitch` | توقف سراسری یا scoped (Owner + Orchestrator) |

## ۵.۲) State machine هر Task

```plain
created → admitted → queued → running → (awaiting_approval) → verifying
        → completed | failed | cancelled | rolled_back
```

هر گذار یک event تولید می‌کند. `awaiting_approval` فقط برای L0/L1. timeout روی `awaiting_approval` = ۲۴ ساعت → auto-cancel + notify.
## ۵.۳) الزامات سخت
mTLS یا OIDC با scope per-capability · replay protection (nonce + 5m window) · rate limit per agent per capability · schema validation ورودی و خروجی · redaction قبل از persist · audit log جدا و append-only · backpressure با queue depth و 429 · deadline propagation · trace\_id در همهٔ لاگ‌ها (OpenTelemetry).

* * *
# ۶) Policy Engine و سطوح استقلال
پیاده‌سازی: OPA/Rego یا موتور داخلی declarative در `gateway/policy/rules.yaml`. تصمیم‌ها همیشه `allow | allow_with_conditions | require_approval | deny` و همیشه با `reason` قابل‌خواندن.
## ۶.۱) ماتریس ریسک → سطح استقلال

| کلاس عملیات | نمونه | سطح | Guardrail اجباری |
| ---| ---| ---| --- |
| Read/Analyze | خواندن metric، تحلیل funnel | L4 | rate limit |
| Internal artifact | نوشتن doc، ADR، backlog | L3 | receipt |
| Reversible config | feature flag، suppression list | L3 | rollback tested + auto-revert on SLO breach |
| Canary publish | انتشار profile روی ۱٪ | L2 | QA gate + probe + auto-rollback |
| Full rollout | ۱۰۰٪ کاربران | L2 | canary سبز ۳۰ دقیقه + error budget موجود |
| Infra mutate | node جدید، terraform apply | L1 | plan diff + Owner approve |
| Money out | ad spend, refund, payout | L1 | budget cap + Owner approve |
| Pricing/Contract | تغییر قیمت، ToS | L0 | فقط پیشنهاد |
| Security-sensitive | rotation، IAM، secret | L1 | ۴ چشم (Security Agent + Owner) |

## ۶.۲) ارتقای خودکار استقلال (Autonomy Ratchet)
این قابلیت را حتماً بساز؛ همین است که سیستم را واقعاً autonomous می‌کند:

```plain
اگر یک capability در ۳۰ اجرای متوالی: 0 rollback، 0 guardrail breach،
100% receipt کامل و انحراف KPI < 2% داشت → پیشنهاد ارتقا از Ln به Ln+1
(حداکثر تا سقف تعیین‌شده در Agent Card، هرگز از L1 برای money/security بالاتر)
هر breach → تنزل فوری یک سطح + قرنطینهٔ ۷۲ ساعته.
```

## ۶.۳) Kill Switch
سه سطح: `global` (همه‌چیز متوقف، فقط read) · `scoped:{agent|capability}` · `budget` (اتمام سقف هزینه). فعال‌سازی از ClickUp (تغییر وضعیت یک تسک مشخص)، از CLI، و خودکار توسط Orchestrator در صورت: نقض SLO بحرانی، spike هزینه > ۳× baseline، الگوی خطای غیرعادی، یا هشدار امنیتی.

* * *
# ۷) لایهٔ Claude Code
## ۷.۱) [CLAUDE.md](http://CLAUDE.md) (حداکثر ۴۰۰ خط)
فقط قوانین پایدار: SSoT، چرخهٔ FSP، مالکیت مسیرها (CODEOWNERS mirror)، DoD، دستورهای تست، سیاست secret، سبک کد، ممنوعیت‌ها. دانش سنگین و متغیر → Skills و Context Pack.
## ۷.۲) Hooks (قطعی، با exit code)

| Hook | ورودی | شکست (exit≠0) وقتی |
| ---| ---| --- |
| SessionStart | session meta | STATE کهنه‌تر از ۲۴ ساعت و sync ناموفق |
| PreToolUse | tool + args | lease نامعتبر، خارج از `owns`، secret در args، capability بدون scope |
| PostToolUse | tool result | schema invalid، secret در خروجی، format شکست |
| PreCommit | diff | نبود task ID، تست قرمز، CODEOWNERS نقض، gitleaks hit، receipt ناقص |
| TaskCompleted | task | verify نشده، evidence نبود، rollback تست‌نشده |
| Stop | session | HANDOFF ننوشته، lease آزاد نشده |

هر hook باید < ۳ ثانیه اجرا شود، خروجی JSON بدهد و خودش event ثبت کند.
## ۷.۳) Skills
هر `SKILL.md` این هدر اجباری را دارد: `name, when_to_load, inputs, outputs, preconditions, policy_refs, steps, tests, evidence, rollback, owner_agent`. Skill بدون تست، merge نمی‌شود. Skillها فقط on-demand load می‌شوند (Context Efficiency یک KPI است).
## ۷.۴) MCP
هر MCP server: allowlist ابزار، timeout، rate limit، read-only پیش‌فرض، write فقط با scope صریح، audit کامل. هرگز credential بلندعمر؛ token کوتاه‌عمر از Vault.
## ۷.۵) Plugin commands
`/fsp-start` `/growth-plan` `/campaign` `/experiment` `/qa-gate` `/handoff` `/incident` `/succession` `/killswitch` `/autonomy-review`

* * *
# ۸) CI/CD (GitHub Actions)

| Workflow | Trigger | وظیفه |
| ---| ---| --- |
| validate | PR + push | schema validation، lint، unit، contract test، receipt lint |
| security | PR + nightly | gitleaks، SCA، SAST، dependency review، policy test |
| compact | hourly | فشرده‌سازی event → STATE.json + archive |
| release | tag | build، canary gate، progressive rollout، auto-rollback |
| mirror | daily | mirror به remote دوم + cold clone artifact |
| heartbeat | \*/15m | بررسی lease منقضی، dead agent detection، auto-release |
| succession | on lease-expiry / member-removed | اجرای پروتکل بخش ۱۱ |
| experiment | \*/30m | guardrail check، auto-stop، readout |
| notify | on events | mirror به ClickUp + کانال هشدار |

OIDC برای احراز هویت Actions؛ هیچ secret بلندعمری در repo. `main` protected، CODEOWNERS اجباری، signed commits.

* * *
# ۹) Control Room در ClickUp (نقشهٔ دقیق)
**اصل کلیدی:** یک Workspace مرکزی، اکانت‌های دیگر به‌عنوان Member. هرگز پروژه را در اکانت‌های جدا کپی نکن.
## ۹.۱) ساختار

```plain
Space: Marzneshin OS
├─ Folder: Control Room     → Lists: Approvals · Incidents · Risks · Kill Switch
├─ Folder: Engineering      → Lists: Agentic Core · Product Reliability · Infra
├─ Folder: Growth & Revenue → Lists: Growth · Revenue · Experiments · Campaigns
├─ Folder: Security & Gov   → Lists: Security Reviews · ADRs · Compliance
└─ Folder: Knowledge        → Docs: MASTER-PLAN v4.0 · BUILD-SPEC v1.0 · Runbooks · Agent Cards
```

## ۹.۲) Custom Fields روی همهٔ Listهای اجرایی
`Owner (agent)` dropdown · `Autonomy Level` L0–L4 · `Trigger` text · `Input Ref` url · `Output Ref` url · `KPI` text · `Evidence` url · `Receipt ID` text · `Rollback` text · `Risk Class` dropdown · `Budget (tokens/USD)` number · `Approval` checkbox · `Blast Radius` dropdown · `Slice` dropdown.
## ۹.۳) Statuses
`Backlog → Claimed → In Progress → Awaiting Approval → Verifying → Done → Rolled Back` (+ `Blocked`).
## ۹.۴) Views و Dashboard
Viewها: «Awaiting Approval» (فیلتر سراسری)، «Autonomy > L2»، «Rollback شده»، «Lease منقضی»، «Guardrail breach».
Dashboard «Revenue Command Center» با کارت‌های: NSM، MRR/NRR، funnel، CAC/LTV، CSR/SLO، experiment readout، agent leverage، هزینهٔ توکن.
## ۹.۵) Sharing و دسترسی چند اکانتی
همهٔ اعضا در همان Workspace به‌عنوان **Member** دعوت شوند (نه Guest؛ Guest به Space دسترسی کامل ندارد). Space روی Public داخل Workspace، Docs روی `Can edit`، Super Agentها با همان اعضا Share شوند. هر عضو در داشبورد شخصی خودش همان تسک‌ها را می‌بیند، چون تسک یکی است و mirror نمی‌شود. Notification: هر عضو Watcher روی Folder مربوطه + یک کانال Chat به‌ازای هر Folder برای رویدادهای خودکار.

**Sync دوطرفه:** GitHub → ClickUp خودکار از workflow `notify`. ClickUp → GitHub فقط برای دو چیز: تغییر فیلد `Approval` و تغییر وضعیت تسک Kill Switch. هیچ چیز دیگری معکوس sync نمی‌شود (I1).

* * *
# ۱۰) تیم Super Agent (پیاده‌سازی در AI Hub)
**ترتیب ساخت اجباری:** ابتدا ۵ ایجنت Tier 0، بعد از سبز شدن VS-4، Tier 1، و در فاز ۳ Tier 2. ساخت هر ۱۷ ایجنت از روز اول = هرج‌ومرج، نه اتوماسیون.
## Tier 0 — عملیات حیاتی

| Agent | Owns | Autonomy | Trigger | KPI | Forbidden |
| ---| ---| ---| ---| ---| --- |
| Orchestrator (CEO Agent) | routing، lease، budget، escalation | L3 (L1 برای money/infra) | schedule 30m + هر رویداد escalation | agent leverage، intervention rate | اجرای مستقیم تغییر در data plane |
| Config Engineer | `configs/**` | L2 | تغییر profile، probe fail | CSR، rollback rate | rollout ۱۰۰٪ بدون canary سبز |
| InfraOps/SRE | `infra/**`، nodes | L1 | alert، capacity، chaos drill | uptime، P95، MTTR | terraform apply بدون plan approve |
| QA Gate | `qa/**`، test matrix | L3 | هر PR و هر release candidate | escaped defects | تأیید خودش روی کار خودش |
| Security & Compliance | `security/**`، policy | L1 | PR، nightly scan، حادثه | secret leaks=0، MTTD | دور زدن ۴ چشم |

## Tier 1 — تاب‌آوری و دانش
Recon (کشف تغییرات محیط/provider) · Panel Automation · Docs & Knowledge (نگهبان CONTEXT-PACK) · **Handoff Guardian** (مهم‌ترین ایجنت پنهان: هیچ جلسه‌ای بدون handoff سالم بسته نمی‌شود، lease زامبی را آزاد می‌کند، continuity score را می‌سازد).
## Tier 2 — موتور درآمد
Lifecycle Growth · Content & Creative · CRO & Experiment · Revenue Intelligence · Sales/Offer · CRM & Retention · Support/Success · Trust/Compliance.
## قواعد مشترک همهٔ ایجنت‌ها
هیچ ایجنتی بدون Agent Card فعال نمی‌شود · هر ایجنت knowledge محدود به `owns` + MASTER-PLAN + BUILD-SPEC دارد · هر ایجنت heartbeat می‌فرستد · هر ایجنت budget روزانه دارد و در ۸۰٪ escalate می‌کند · هیچ ایجنتی خودش را تأیید نمی‌کند (separation of duties) · هر ایجنت باید بتواند در یک جمله بگوید «چرا این کار را کردم» و آن جمله در receipt ثبت شود.

* * *
# ۱۱) تداوم عملیات: خروج اعضا و ریسک Bus-Factor
این بخش را جدی بگیر؛ همان چیزی است که اکثر سیستم‌های agentic در آن می‌میرند.
## ۱۱.۱) Succession Protocol (خودکار)

```plain
TRIGGER: member removed | lease expired > TTL | 3 heartbeat متوالی گم‌شده | offboarding flag در ClickUp

STEP 1  FREEZE      کارهای در جریان آن عضو/ایجنت → status Blocked، lease با fencing token جدید باطل
STEP 2  REVOKE      حذف دسترسی: ClickUp، GitHub، Vault، A2A scope؛ rotation همهٔ secretهای لمس‌شده
STEP 3  RECONSTRUCT بازسازی وضعیت فقط از receipts + events (نه از حافظهٔ آن شخص)
STEP 4  REASSIGN    Orchestrator بر اساس capability match در Registry مالک جدید تعیین می‌کند
STEP 5  BACKFILL    Docs Agent شکاف دانش را از receipts به Runbook تبدیل می‌کند
STEP 6  VERIFY      اجرای smoke test مالکیت جدید؛ تا سبز نشدن، workstream در حالت L1
STEP 7  REPORT      ADR + گزارش در ClickUp + به‌روزرسانی CODEOWNERS
```

## ۱۱.۲) اصول ضدشکنندگی
*   **هیچ دانش انحصاری انسانی مجاز نیست.** هر چیزی که فقط در سر یک نفر است، یک incident است. Docs Agent هفتگی «knowledge concentration report» می‌سازد.
*   **Two-key rule:** هر مسیر بحرانی حداقل دو مالک دارد (یک ایجنت + یک انسان یا دو ایجنت مستقل).
*   **Dead-man switch:** اگر Owner انسانی ۷۲ ساعت پاسخ ندهد، همهٔ capabilityهای L1 به‌صورت خودکار به «queue + hold» می‌روند، کارهای L2/L3 ادامه می‌یابند، و سیستم در حالت safe-continue کار می‌کند. بعد از ۱۴ روز، تنزل به read-only.
*   **Cold restore drill ماهانه:** از روی mirror + receipts، یک محیط تازه بالا بیاور و ثابت کن ۱۰۰٪ وضعیت بازسازی می‌شود. اگر نشد، سیستم واقعاً autonomous نیست.
*   **Agent succession:** هر ایجنت یک `standby_for` دارد؛ اگر ایجنتی سه بار پشت‌سرهم fail کرد، standby با autonomy یک سطح پایین‌تر جایگزین می‌شود.

* * *
# ۱۲) حلقهٔ اتوماسیون کامل (بدون انسان)
## ۱۲.۱) Tick سراسری (هر ۳۰ دقیقه، Orchestrator)

```plain
1 SENSE     خواندن SLO، funnel، revenue، tickets، error budget، هزینه
2 DIAGNOSE  مقایسه با baseline و هدف؛ تشخیص leak/regression/فرصت
3 DECIDE    انتخاب حداکثر ۳ اقدام با بیشترین expected value ÷ risk
4 ROUTE     ساخت A2A task با idempotency و deadline
5 EXECUTE   ایجنت‌های تخصصی به‌صورت موازی (حداکثر ۵ همزمان)
6 VERIFY    QA/Security gate + probe واقعی
7 COMMIT    receipt + event + commit atomic + ClickUp mirror
8 LEARN     به‌روزرسانی backlog فرضیه، autonomy ratchet، هزینه/توکن
9 GUARD     اگر هر guardrail قرمز → rollback + قرنطینه + escalate
```

## ۱۲.۲) تنها موارد ورود انسان
تغییر قیمت · خروج پول · تغییر زیرساخت غیرقابل‌بازگشت · تغییر ToS/Privacy · حادثهٔ امنیتی Sev1 · فعال/غیرفعال کردن kill switch. بقیهٔ ۹۵٪ باید بدون انسان بچرخد. اگر intervention rate از ۵٪ کارها بالاتر رفت، آن یک باگ است نه یک ویژگی: علتش را به‌عنوان تسک ثبت کن.

* * *
# ۱۳) Growth، Revenue و Experimentation (پیاده‌سازی)
## ۱۳.۱) Event Taxonomy (حداقل مجموعه، first-party)
`page_view · signup_started · trial_created · client_guide_viewed · config_downloaded · first_connection_attempt · first_connection_success · connection_health_sample · checkout_started · payment_succeeded · provision_completed · renewal_due · renewal_succeeded · usage_drop · support_contact · refund_requested · referral_shared · reactivated`

هر event: name, actor(anon key), ts, source, campaign, consent\_state, schema\_version, correlation\_id. ذخیرهٔ محتوای ترافیک و مقصد کاربر **ممنوع**.
## ۱۳.۲) North Star
**تعداد کاربران پرداختی با حداقل یک اتصال موفق و پایدار در پنجرهٔ ۷ روزه.** همهٔ داشبوردها باید بتوانند به این عدد تجزیه شوند.
## ۱۳.۳) Unit economics (فرمول‌های اجرایی در `analytics/models/`)

```plain
GrossProfitPerUser = ARPU − infra/user − payment_fee − support_cost
LTV = ARPU × gross_margin × expected_lifetime_months
Targets: LTV:CAC > 3 · CAC payback < 3mo · gross_margin > 70%
Stop-loss: هر کمپین با CAC > 1.5× هدف در ۴۸ ساعت خودکار متوقف می‌شود
```

## ۱۳.۴) Experiment Engine
قرارداد آزمایش دقیقاً طبق MASTER-PLAN §۹.۲. اضافه‌های الزامی: محاسبهٔ خودکار sample size قبل از شروع (power ۰.۸، alpha ۰.۰۵)، sequential testing با always-valid p-value برای توقف زودهنگام امن، SRM check (sample ratio mismatch) در هر readout، و «negative result» هم باید مستند شود. آزمایش بدون guardrail = قمار با داده؛ workflow `experiment` هر ۳۰ دقیقه guardrail را چک و در صورت نقض، خودکار stop و rollback می‌کند.

* * *
# ۱۴) Observability، SLO و Error Budget

| SLI | SLO | پنجره | واکنش نقض |
| ---| ---| ---| --- |
| Connection Success Rate | ≥ ۹۸٪ | ۷ روز غلتان | فریز release، Config Agent به L1 |
| P95 latency | ≤ هدف مسیر | ۲۴ ساعت | reroute + probe |
| Provisioning time | ≤ ۶۰ ثانیه | ۲۴ ساعت | صف پرداخت بررسی شود |
| Checkout success | ≥ ۹۵٪ | ۷ روز | مسیر پرداخت جایگزین |
| A2A task success | ≥ ۹۷٪ | ۷ روز | تنزل autonomy |
| Receipt completeness | ۱۰۰٪ | همیشه | build شکست |

Error budget policy: مصرف > ۵۰٪ → فقط کارهای reliability. > ۱۰۰٪ → همهٔ featureها و کمپین‌ها فریز تا بازیابی. Stack: Prometheus + Grafana + Loki + OpenTelemetry، probeهای واقعی از چند شبکه، chaos drill ماهانه.

* * *
# ۱۵) امنیت و حریم خصوصی
GitHub App یا fine-grained token (Classic PAT ممنوع) · OIDC برای Actions · SOPS+age یا Vault با token کوتاه‌عمر · gitleaks در CI و در PreCommit · CODEOWNERS + protected main + signed commits · A2A با mTLS/OIDC + scope + replay protection · least privilege برای هر ایجنت · حداقل داده، no-content-logs، retention مشخص و اجباری (event خام ۹۰ روز، aggregate نامحدود) · consent state در هر event · هر حادثه: Detect → Contain → Eradicate → Recover → Postmortem با ADR.

**Prompt injection defense (اجباری برای سیستم agentic):** هر محتوای خارجی (تیکت، ایمیل، صفحهٔ وب، پیام کاربر) به‌عنوان **داده** برچسب می‌خورد نه دستور؛ ایجنت‌ها هرگز capability را از محتوای ورودی نمی‌گیرند؛ هر ابزار پرریسک فقط از مسیر policy engine صدا زده می‌شود؛ خروجی ایجنت قبل از اجرا schema-validate می‌شود.

* * *
# ۱۶) استراتژی تست و پذیرش

| لایه | تست | معیار پذیرش |
| ---| ---| --- |
| Unit | schema، policy rule، adapter | coverage ≥ ۸۰٪ روی gateway و adapters |
| Contract | هر adapter در برابر fake + sandbox | ۱۰۰٪ opها |
| Integration | A2A end-to-end با ۳ ایجنت | task success ≥ ۹۷٪ |
| Chaos | کشتن ایجنت وسط کار، انقضای lease، قطع provider | بازیابی خودکار < ۱۵ دقیقه، بدون کار تکراری |
| Continuity | حذف یک عضو، restore سرد | بازسازی ۱۰۰٪ وضعیت |
| Security | gitleaks، SAST، injection suite | صفر یافتهٔ high |
| Business | canary روی funnel واقعی | بدون افت guardrail |

* * *
# ۱۷) ترتیب ساخت — Vertical Slices
هیچ‌وقت دو اسلایس هم‌زمان. هر اسلایس با DoD کامل بسته می‌شود.

| # | اسلایس | تحویل‌دادنی | DoD |
| ---| ---| ---| --- |
| VS-1 | Spine | repo، [CLAUDE.md](http://CLAUDE.md)، STATE/HANDOFF/events، receipts، ۶ hook، validate+compact+mirror | یک تسک ساختگی از CLAIM تا HANDOFF کامل با receipt سبز |
| VS-2 | Gateway MVP | A2A Gateway با ۴ endpoint، Registry، یک Agent Card، policy engine حداقلی | یک task واقعی میان دو ایجنت با audit و idempotency |
| VS-3 | Control Room | Space/Folder/List/Fields/Statuses/Views + sync یک‌طرفه + approval برگشتی | تغییر در GitHub در < ۶۰ ثانیه در ClickUp دیده شود |
| VS-4 | Tier 0 Agents | ۵ ایجنت با کارت، budget، heartbeat، QA gate | smoke test دو اکانتی سبز |
| VS-5 | Config Pipeline | canary ۱٪→۱۰٪→۵۰٪→۱۰۰٪ + probe + auto-rollback | یک rollback واقعی تست‌شده و ثبت‌شده |
| VS-6 | Continuity | succession workflow، dead-man switch، cold restore drill | حذف شبیه‌سازی‌شدهٔ یک عضو بدون توقف پروژه |
| VS-7 | Growth Spine | event taxonomy، checkout، funnel dashboard، journey اول | NSM قابل محاسبه از داده واقعی |
| VS-8 | Experiment Loop | experiment engine + guardrail + readout + ۳ تست کم‌ریسک | یک تصمیم ship/kill مستند با evidence |
| VS-9 | Revenue Command Center | داشبوردهای §۸ MASTER-PLAN + unit economics | هر عدد به event خام قابل ردیابی |
| VS-10 | Autonomy Ratchet | ارتقا/تنزل خودکار سطح استقلال | ۷۲ ساعت اجرای بدون مداخله |

* * *
# ۱۸) Trade-off Register (صریح، نه پنهان)
«بدون trade-off» وجود ندارد؛ هدف واقعی این است: **trade-off آگاهانه، محدود، ثبت‌شده و قابل‌برگشت.**

| انتخاب | منفعت | هزینه | مهار |
| ---| ---| ---| --- |
| GitHub SSoT | اکوسیستم، Actions، audit رایگان | وابستگی به پلتفرم | mirror روزانه + cold clone + adapter |
| A2A Gateway مستقل | استقلال ایجنت‌ها، audit کامل | پیچیدگی عملیاتی | شروع با vertical slice، نه پلتفرم کامل |
| Event sourcing | replay، تعارض کمتر | حجم و نیاز به compact | compact ساعتی + archive + schema version |
| اتوماسیون کامل | سرعت و هزینهٔ کمتر | blast radius خطا | autonomy levels + kill switch + rollback |
| Sequential testing | تصمیم سریع‌تر | پیچیدگی آماری | always-valid p-value + SRM check |
| Personalization | conversion بالاتر | ریسک privacy | first-party + consent + حداقل داده |
| چند مسیر پروتکل | تاب‌آوری | هزینه و نگهداری بیشتر | اولویت بر اساس SLO، حداکثر ۳ مسیر |
| Multi-agent | تخصص و موازی‌سازی | هزینهٔ توکن و هماهنگی | budget per agent + Context Efficiency KPI |

* * *
# ۱۹) Definition of Done نهایی
یک initiative فقط وقتی Done است که همهٔ این‌ها درست باشند: مسئله و hypothesis روشن · owner/scope/budget/success metric مشخص · artifact در مسیر درست commit شده · تست فنی، امنیتی و تجاری اجرا شده · receipt + evidence + event + HANDOFF ثبت · CI سبز · rollback **عملاً تست شده** · dashboard و alert ساخته شده · ADR یا experiment report ثبت · ClickUp mirror شده · lease آزاد.

* * *
# ۲۰) خروجی مورد انتظار از Claude Opus 5
در پاسخ اول، دقیقاً این‌ها را بده و بعد بلافاصله VS-1 را بساز:

1. **Repo scaffold کامل** با محتوای واقعی فایل‌ها (نه placeholder).
2. **`CLAUDE.md`** **نهایی** + `CONTEXT-PACK.md` اولیه + `STATE.json` صفر.
3. **شش hook اجرایی** با تست.
4. **سه workflow** (`validate`, `compact`, `mirror`) که سبز شوند.
5. **یک receipt نمونهٔ واقعی** از یک تسک end-to-end.
6. **ADR-001** برای انتخاب‌های معماری که خودت گرفتی.
7. **گزارش GAP:** هر جای این سند که با واقعیت ابزارها نمی‌خواند، صریح بگو و جایگزین پیشنهاد بده. سکوت کردن روی شکاف = نقض قرارداد.

هر پاسخ با یک بلوک وضعیت تمام می‌شود:

```plain
SLICE: VS-x | STATUS: green|amber|red
DONE: ... | NEXT: ... | BLOCKERS: ... | RECEIPTS: ... | TOKENS: ...
```

* * *
## پنج قانون آهنین
1. هیچ کانفیگی بدون QA به کاربر نمی‌رسد.
2. هیچ کمپینی بدون hypothesis و stop condition اجرا نمی‌شود.
3. هیچ جلسه‌ای بدون HANDOFF تمام نمی‌شود.
4. هیچ secretی وارد مخزن نمی‌شود.
5. هیچ تصمیمی بدون owner، evidence و rollback پذیرفته نمی‌شود.