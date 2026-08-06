# BUILD-SPEC v2.0 — Marzneshin Autonomous OS
## Implementation Brief for Claude Opus 5 (Executable Contract)

> **ورودی مرجع:** MASTER-PLAN v4.0 FINAL · GAP-REPORT-001 · ADR-001
> **این سند:** قرارداد اجرایی (executable contract) و **حاکم** برای مدلی که پیاده‌سازی می‌کند.
> **قاعدهٔ کلی:** هرچه در MASTER-PLAN «چه چیزی» است، در این سند «دقیقاً چگونه» است. در تعارض، این سند حاکم است.
> **جایگاه v2.0:** این سند جانشین کامل v1.0 است، نه پیوست آن. v1.0 بازنشسته می‌شود. هیچ‌جای این سند به v1.0 ارجاع نمی‌دهد؛ هر چیزی که برای ساخت سیستم لازم است، اینجا هست.

* * *
# ۰) قرارداد با مدل پیاده‌ساز (بخوان، بعد شروع کن)
**تو Owner فنی این پروژه‌ای، نه دستیار.** بدون پرسیدن سؤال‌های بدیهی شروع کن. جایی که سند ساکت است، تصمیم بگیر، تصمیم را در `decisions/ADR/` ثبت کن و ادامه بده. سکوت کردن روی شکاف = نقض قرارداد.

**پروتکل پاسخ در هر جلسه (اجباری):**

```plain
1. SYNC        → state/STATE.json + HANDOFF.md + receipts اخیر + وضعیت kill switch را بخوان
2. GAP SCAN    → فاصلهٔ وضعیت فعلی تا Definition of Done اسلایس جاری
3. CLAIM       → lease بگیر (workstream-level، TTL 90m، fencing token جدید)
4. PLAN        → حداکثر ۷ گام، هر گام با artifact مشخص
5. SIM         → تغییر را ابتدا در sim/ اجرا کن؛ قرمز = ورود به production ممنوع
6. EXECUTE     → کد/کانفیگ واقعی، نه شبه‌کد، نه TODO
7. VERIFY      → تست اجرا شود، خروجی واقعی گزارش شود
8. EMIT        → event + receipt (با prev_receipt_hash) + commit atomic
9. HANDOFF     → HANDOFF.md بازنویسی شود، lease آزاد شود
```

**ممنوعیت‌های مطلق برای مدل پیاده‌ساز:**
*   تحویل فایل خالی، `pass`، `TODO`، یا mock به‌جای پیاده‌سازی واقعی.
*   ادعای «تست پاس شد» بدون خروجی واقعی تست.
*   ساخت بیش از یک اسلایس هم‌زمان.
*   نوشتن secret در repo/prompt/log/artifact.
*   تغییر فایل خارج از `owns` اسلایس جاری بدون ADR.
*   ورود کد جدید به مسیر production بدون سبز شدن سناریوی مربوطه در `sim/`.
*   ادامه دادن وقتی وضعیت یک کنترل ایمنی (kill switch، lease، budget، probe) **قابل خواندن نیست**. «نمی‌دانم» هم‌ارز «متوقف شو» است.

**تعریف موفقیت نهایی:** یک سیستم که ۷۲ ساعت بدون مداخلهٔ انسانی کار کند، خودش تشخیص دهد، تصمیم بگیرد، اجرا کند، تأیید کند، در صورت خطا rollback کند و همهٔ اینها را با evidence قابل‌ممیزی ثبت کند — و این ادعا **قبل از** ریسک‌کردن کاربر واقعی، در `sim/` با seed و به‌صورت بازتولیدشدنی اثبات شود.

## ۰.۱) تغییرات نسبت به v1.0 (جدول ممیزی ادغام)

| # | تصمیم ADR-001 | خلاصه | بخش‌های بازنویسی‌شده در v2.0 |
| ---| ---| ---| --- |
| D1 | Transport سه‌لایه | Gateway از مسیر بحرانی خارج؛ T1 git، T2 moxt، T3 http اختیاری | §۲.۱ · **§۵ (کامل)** · §۴ · §۱۷ (VS-3, VS-12) · I14 |
| D2 | GitHub تنها SSoT | Moxt سطح کار و کنترل، نه منبع حقیقت | §۱.۳ (I1) · §۲.۱ · §۸ · §۹ |
| D3 | Control Room بومی Moxt | ClickUp اختیاری پشت adapter | **§۹ (کامل)** · §۴ · §۱۸ |
| D4 | حذف `seq` سراسری | ULID + `actor_seq` + پارتیشن نوشتن هر actor | **§۳.۲ (کامل)** · §۳.۱ · §۷.۲ · I17 |
| D5 | Fail-closed سراسری | kill switch پنج‌مسیره؛ «نمی‌دانم» = «متوقف شو» | **§۶.۳ (کامل)** · §۵.۷ · §۶.۴ · §۰ · I12 |
| D6 | Simulation Harness درجه‌یک | ۷۲ ساعت در ۶۰ ثانیه، seed-دار | **§۱۶ (جدید و کامل)** · §۱۷ (VS-2) · §۳.۳ · I11 |
| D7 | Two-key = دو تبار مستقل | Adversarial Reviewer + CODEOWNERS چهارمسیره | **§۱۱.۲** · §۱۰ (Tier 0) · §۱۵.۱ |
| D8 | بازچینی Tier 0 و اسلایس‌ها | Tier 0 هفت‌نفره؛ ۱۲ اسلایس با ترتیب اصلاح‌شده | **§۱۰ (کامل)** · **§۱۷ (کامل)** |
| D9 | Idempotency/Receipt/Taint | سه‌کلاسه · پنج‌وضعیته و زنجیره‌ای · taint | **§۳.۳ (کامل)** · **§۳.۵ (کامل)** · §۳.۴ · §۱۵.۲ · I3 · I15 · I16 |
| D10 | زبان و مالکیت اسناد | spec فارسی، کد/schema/commit انگلیسی | این سند · §۷.۱ · §۷.۳ |

| GAP | اصلاح در | GAP | اصلاح در |
| ---| ---| ---| --- |
| G1 بستر اجرا/SPOF | §۵ کامل | G11 مهاجرت schema | §۳.۷ |
| G2 سازمان تک‌نفره | §۱۱.۲ | G12 قدرت آماری canary | §۵.۷ |
| G3 kill switch fail-open | §۶.۳ | G13 metric gaming | §۱۰.۴ |
| G4 معنای idempotency | §۳.۵ | G14 ترکیب Tier | §۱۰ |
| G5 receipt completeness | §۳.۳ · §۱۴ · I3 | G15 ترتیب اسلایس | §۱۷ |
| G6 `seq` سراسری | §۳.۲ | G16 SENSE بدون داده | §۱۲.۰ |
| G7 نبود محیط شبیه‌سازی | §۱۶ | G17 شواهد ratchet | §۶.۲ |
| G8 مدل هزینه | §۶.۴ | G18 زنجیرهٔ receipt | §۳.۳ |
| G9 بودجهٔ hook | §۷.۲ | G19 نقطهٔ کور انطباق | §۱۵.۳ |
| G10 معماری injection | §۱۵.۲ | — | — |

* * *
# ۱) دامنه، خارج از دامنه، و اصول ثابت
## ۱.۱) In scope
Control Plane (Orchestrator + Transport سه‌لایه + Policy Engine) · State Plane (GitHub SSoT + Events + Receipts + Receipt Chain) · Execution Layer (Claude Code + Hooks + Skills + MCP + Subagents) · Simulation Plane (`sim/` — ساعت مجازی، fakes، سناریو، chaos) · Control Room (Moxt Workflow، ClickUp اختیاری) · Growth/Revenue/Experiment Engine · Observability + Security + Governance + Compliance Register.

## ۱.۲) Out of scope (صریحاً نساز)
UI اختصاصی داشبورد در فازهای ۰–۳ (از Moxt Mini App + Grafana استفاده کن) · CRM اختصاصی · Data warehouse سفارشی (DuckDB/Postgres کافی است) · هر microservice که با یک module قابل انجام است · **A2A Gateway مبتنی بر FastAPI/Postgres/Redis پیش از VS-12** — تا زمانی که latency مسیرهای T1/T2 اثباتاً محدودکننده نشده باشد، ساخت آن اتلاف است.

## ۱.۳) Invariants (نقض = build شکست‌خورده)

| # | Invariant | مکانیزم اجبار |
| ---| ---| --- |
| I1 | GitHub تنها منبع حقیقت | Moxt/ClickUp فقط سطح کار و mirror؛ نوشتن معکوس ممنوع جز دو استثنای §۹.۵ |
| I2 | هر worker بی‌حالت است | SessionStart hook اجباری SYNC می‌کند |
| I3 | هر تسک **دقیقاً یک** receipt دارد با `status` معتبر | `hooks/task_complete.py` بدون receipt exit 1 · reaper هر ۱۵ دقیقه tombstone `crashed` می‌نویسد · KPI مستقل `crash_rate < 2%` |
| I4 | هیچ release بدون canary آماری‌معتبر | release workflow بدون canary gate با `n ≥ n_min` fail |
| I5 | هیچ کمپین بدون stop condition | campaign adapter schema validation |
| I6 | هیچ secret خام | gitleaks + PreToolUse redaction + PreCommit روی staged diff |
| I7 | هر تصمیم reversible | `rollback` فیلد اجباری در receipt، `tested: true` |
| I8 | trade-off ثبت‌شده، نه صفر | `decisions/TRADEOFF-REGISTER.md` — **این invariant بر هر خواستهٔ «صفر trade-off» حاکم است** |
| I9 | هیچ ادعای بازاریابی بدون evidence | Trust/Compliance gate روی هر content artifact |
| I10 | blast radius محدود | policy engine + autonomy level + budget reservation |
| I11 | هیچ کد جدیدی بدون سبزی در `sim/` به production نمی‌رود | `validate` workflow سناریوی مرتبط را اجرا می‌کند؛ قرمز = merge ممنوع |
| I12 | همهٔ کنترل‌های ایمنی fail-closed هستند | ناخوانا بودن وضعیت kill switch/lease/budget/probe → توقف عملیات با blast radius > L3 |
| I13 | هر KPI یک counter-KPI با **مالک متفاوت** دارد | CI رد می‌کند اگر `counter_kpi_owner == agent.id` یا counter_kpi خالی باشد |
| I14 | هیچ قابلیت ایمنی‌ای فقط روی T3 زنده نیست | contract test ایمنی روی T1 اجرا می‌شود؛ T3 در تست خاموش است |
| I15 | زنجیرهٔ receipt پیوسته و ضددستکاری است | `scripts/verify.py --chain` در هر PR و nightly |
| I16 | محتوای `untrusted` هرگز capability نمی‌سازد | `input_provenance` اجباری · هر ابزار جهش‌دهنده با پارامتر مشتق از untrusted سقف L1 |
| I17 | یک نویسنده به ازای هر مسیر | پارتیشن `state/events/{date}/{actor}.ndjson` + `owns` در Agent Card + اجبار در `hooks/pre_tool.py` |
| I18 | هر event تاریخی خواندنی می‌ماند | upcaster تابع‌خالص در `analytics/schemas/migrations/`؛ حذف فیلد بدون upcaster = CI قرمز |

* * *
# ۲) معماری هدف و ساختار مخزن
## ۲.۱) لایه‌ها

```plain
L5  Governance     Owner + Moxt Approvals + Kill Switch (5 paths) + RECOVERY escrow
L4  Orchestration  Orchestrator Agent + Adaptive Scheduler + Lease Manager + Budget Ledger
L3  Protocol       Transport (T1 git · T2 moxt · T3 http) + Agent Registry
                   + Policy Engine + Taint Enforcer + Audit Log
L2  Execution      Claude Code · Skills · Hooks · MCP · Subagents
L1  State          GitHub (SSoT) · Event Log (partitioned) · Receipt Chain · Artifacts
L0  Systems        Marzneshin/Marznode · Payments · Analytics · Observability
LS  Simulation     sim/ — آینهٔ L0 با ساعت مجازی و fake adapters (مسیر تست همهٔ لایه‌ها)
```

قوانین لایه‌بندی:
*   هر لایه فقط با لایهٔ مجاور صحبت می‌کند. L2 هرگز مستقیم به L0 دست نمی‌زند، همیشه از Adapter در L1 عبور می‌کند.
*   L3 یک **قرارداد** است نه یک **سرویس**. سه پیاده‌سازی transport دارد که همهٔ آن‌ها یک envelope مشترک (§۳.۵) دارند. مرگ هر transport فقط latency را بدتر می‌کند، هرگز سیستم را متوقف نمی‌کند.
*   `LS` با همان interface §۴ به L2 وصل می‌شود؛ سوییچ بین production و simulation یک متغیر محیطی است (`MARZ_WORLD=prod|sim`)، نه یک شاخهٔ کد.

## ۲.۲) ساختار مخزن (بساز دقیقاً همین)

```plain
marzneshin-ops/
├─ CLAUDE.md                      # قوانین پایدار، < 400 خط
├─ CONTEXT-PACK.md                # وضعیت فشرده برای شروع جلسه
├─ MASTER-PLAN.md                 # سند استراتژی (read-only)
├─ BUILD-SPEC.md                  # همین سند (حاکم)
├─ RECOVERY.md                    # مسیر خروج انسانی غیرفنی (§۱۱.۲)
├─ CODEOWNERS                     # چهار مسیر انسانی، بقیه مالک ایجنتی
├─ state/
│  ├─ STATE.json                  # snapshot compact شده
│  ├─ HANDOFF.md                  # آخرین وضعیت انسانی‌خوان
│  ├─ KILL                        # مسیر K1 kill switch (atomic، نسخه‌دار)
│  ├─ events/YYYY-MM-DD/{actor}.ndjson    # append-only، یک نویسنده per file
│  ├─ a2a/
│  │  ├─ inbox/{agent}/{ulid}.json        # T1 transport — dispatch
│  │  ├─ outbox/{agent}/{ulid}.json       # نتیجه/پیام میان‌مرحله‌ای
│  │  └─ processed/{agent}/{ulid}.json    # آرشیو با receipt ref
│  ├─ locks/{workstream}.lock.json
│  ├─ budget/ledger.json          # دفتر رزرو/تسویه (§۶.۴)
│  └─ archive/
├─ receipts/YYYY/MM/T-xxxx.json   # زنجیره‌ای با prev_receipt_hash
├─ decisions/ADR/ADR-xxx.md + TRADEOFF-REGISTER.md + GAP-REPORT-xxx.md
├─ agents/{cards,policies,prompts}/
├─ skills/{fsp-session,growth-lifecycle,revenue-dashboard,experiment-loop,
│          campaign-launch,qa-gate,security-review,github-atomic-commit,
│          handoff,sim-run,adversarial-review}/SKILL.md
├─ hooks/{session_start,pre_tool,post_tool,pre_commit,pre_push,
│         task_complete,stop}.py
├─ plugins/marzneshin-ops/
├─ sim/                           # Simulation Harness (§۱۶) — VS-2
│  ├─ clock.py world.py chaos.py report.py
│  ├─ fakes/{github,moxt,clickup,marzneshin,payments,analytics,
│  │         messaging,observability,vault}.py
│  └─ scenarios/*.yaml
├─ gateway/                       # T3 اختیاری — VS-12، ساخت آن قبل از VS-12 ممنوع
│  ├─ app.py routes/ policy/ registry/ auth/ store/ tests/
├─ adapters/{github,moxt,clickup,marzneshin,payments,analytics,
│            messaging,observability,vault}/
├─ mcp/{github,moxt,clickup,product,analytics,observability}.json
├─ growth/{personas,journeys,campaigns,offers,content,experiments}/
├─ analytics/
│  ├─ events/ models/ dashboards/
│  └─ schemas/                    # JSON Schema Draft 2020-12
│     └─ migrations/v1_0__v1_1.py ...   # upcaster تابع خالص (§۳.۷)
├─ security/
│  ├─ iam/ policies/
│  └─ compliance/                 # register، playbook قانونی، data residency (§۱۵.۳)
├─ configs/{templates,profiles,releases}/
├─ infra/{terraform,ansible,compose}/
├─ scripts/
│  ├─ lib/{state.py,events.py,receipts.py,leases.py,taint.py,
│  │       budget.py,transport.py,redact.py}     # کتابخانهٔ مشترک، بدون تکرار منطق
│  ├─ fsp.py compact.py context_pack.py verify.py experiment_guard.py
│  ├─ succession.py killswitch.py reaper.py sim.py autonomy_review.py
└─ .github/workflows/{validate,compact,release,mirror,security,notify,
                      experiment,heartbeat,succession,sim-nightly,a2a-dispatch}.yml
```

قانون ساختاری: هر منطقی که در بیش از یک script لازم است، به `scripts/lib/` می‌رود. hookها و workflowها **فقط** لایهٔ نازک روی `scripts/lib/` هستند؛ کپی‌کردن منطق state/event/receipt در چند فایل ممنوع است.

* * *
# ۳) قراردادهای داده (Canonical Schemas)
همهٔ اینها را در `analytics/schemas/` به‌صورت JSON Schema Draft 2020-12 بنویس و در CI اعتبارسنجی کن. `schema_version` سراسری این نسخه: `2.0.0`.

## ۳.۱) STATE.json

```json
{
  "schema_version": "2.0.0",
  "generated_at": "2026-07-28T12:00:00Z",
  "compacted_from": {"until_ts": "2026-07-28T11:59:59Z", "event_count": 18422,
                     "actor_seq_watermarks": {"orchestrator": 4821, "config-engineer": 1902}},
  "phase": "P1-agentic-core",
  "active_slice": "VS-2",
  "tick_level": "A",
  "transport_health": {
    "T1": {"status": "up",   "last_ok_at": "2026-07-28T11:58:00Z", "consecutive_failures": 0},
    "T2": {"status": "up",   "last_ok_at": "2026-07-28T11:59:10Z", "consecutive_failures": 0},
    "T3": {"status": "absent","last_ok_at": null, "consecutive_failures": 0},
    "active_default": "T2",
    "fallback_to": "T1"
  },
  "workstreams": {
    "agentic-core": {
      "owner_agent": "orchestrator",
      "lease": {"holder": "agent:config-engineer", "fencing_token": 42,
                "expires_at": "2026-07-28T13:20:00Z", "heartbeat_at": "2026-07-28T11:59:40Z"},
      "open_tasks": ["T-0142"],
      "blocked_by": [],
      "last_receipt": "receipts/2026/07/T-0141.json",
      "receipt_chain_head": "sha256:9f2c...",
      "receipt_chain_length": 141,
      "health": "green"
    }
  },
  "kpis": {"connection_success_rate": 0.987, "activation_rate": 0.41, "nsm": 1284,
           "receipt_coverage": 1.0, "crash_rate": 0.008, "intervention_rate": 0.031,
           "agent_leverage": 6.4, "context_efficiency": 0.72},
  "counter_kpis": {"unsubscribe_rate": 0.004, "support_contact_per_user": 0.11,
                   "refund_rate": 0.006, "rollback_rate": 0.02},
  "kill_switch": {
    "global": false,
    "scoped": [],
    "read_from": ["K1:state/KILL", "K2:gh-var", "K4:cli"],
    "read_at": "2026-07-28T11:59:55Z",
    "freshness_s": 5,
    "fail_closed_engaged": false
  },
  "budget": {
    "window": "2026-07-28",
    "workspace": {"tokens_cap": 4000000, "tokens_reserved": 210000,
                  "tokens_settled": 1830000, "usd_cap": 90, "usd_settled": 38.4},
    "forecast": {"tokens_eod": 3600000, "usd_eod": 76.2, "breach_probability": 0.18},
    "state": "normal"
  },
  "sim": {"last_run_at": "2026-07-28T09:40:00Z", "suite": "full",
          "seeds": [11, 27, 43], "pass": 34, "fail": 0, "score": 0.97},
  "open_risks": [{"id": "R-07", "severity": "med", "owner": "infraops-sre",
                  "mitigation_task": "T-0150"}],
  "degraded_sense": []
}
```

قواعد: STATE.json **مشتق** است، هرگز منبع حقیقت نیست — همیشه از event log و receipt chain بازتولیدشدنی. `compact` هر ساعت آن را می‌سازد و `actor_seq_watermarks` تضمین می‌کند هیچ event ای در فاصلهٔ دو compaction گم نشده باشد (شکاف در دنبالهٔ یک actor = هشدار `event.gap.detected`).

## ۳.۲) Event (append-only، NDJSON، پارتیشن‌شده)
مسیر: `state/events/{YYYY-MM-DD}/{actor_id}.ndjson` — **هر actor فقط فایل خودش را می‌نویسد.**

```json
{"event_id":"01K1G7Z8N4QW3XJ2R5Y6B7C8D9",
 "actor_seq":4822,
 "ts":"2026-07-28T11:58:41.204Z",
 "type":"task.completed",
 "schema_version":"2.0.0",
 "actor":{"kind":"agent","id":"qa-gate","session":"S-91",
          "lineage":"opus5/qa-gate@3","model":"claude-opus-5"},
 "subject":{"kind":"task","id":"T-0142"},
 "correlation_id":"01K1G7T0000000000000000000",
 "causation_id":"01K1G7Y1M2P3Q4R5S6T7U8V9W0",
 "transport":"T1",
 "tick_level":"A",
 "trust":"internal",
 "payload":{"verdict":"pass","checks":7},
 "inputs_hash":"sha256:4b1d...",
 "seed":null,
 "world":"prod",
 "redacted":false,
 "redaction_map":[]}
```

قواعد سخت:
*   **هرگز edit، هرگز delete.** compaction فقط snapshot جدید می‌سازد و event خام را لمس نمی‌کند.
*   `event_id` = **ULID** → مرتب‌شدنی بر اساس زمان، بدون هیچ هماهنگی بین نویسندگان. هیچ `seq` سراسری وجود ندارد و هیچ CAS سراسری لازم نیست.
*   `actor_seq` = شمارندهٔ یکنواخت صعودی **به‌ازای هر actor**، بدون شکاف. تنها ابزار تشخیص event گم‌شده.
*   ترتیب **علّی** از `causation_id` استنتاج می‌شود، نه از ترتیب کلی. ترتیب کلی هرگز مورد نیاز این سیستم نبوده.
*   `world` = `prod|sim`؛ event شبیه‌سازی هرگز در پارتیشن production نوشته نمی‌شود (`state/events/sim/...`).
*   `trust` از منبع رویداد ارث می‌برد (§۱۵.۲). event با `trust: untrusted` هرگز به‌عنوان trigger یک capability جهش‌دهنده استفاده نمی‌شود.
*   `redaction_map` فهرست مسیرهای JSONPath پاک‌شده است؛ حذف بدون ثبت ممنوع.

## ۳.۳) Receipt (بدون این، کار Done نیست)
`receipt.status` اجباری با پنج مقدار — تسک بدون receipt وجود ندارد، حتی وقتی ایجنت وسط کار می‌میرد:

| status | معنا | نویسنده |
| ---| ---| --- |
| `complete` | کار تمام، verify سبز | ایجنت |
| `failed` | کار تمام، نتیجه منفی — receipt کامل و معتبر است | ایجنت |
| `abandoned` | لغو آگاهانه، دلیل ثبت‌شده | ایجنت یا Orchestrator |
| `crashed` | tombstone (lease منقضی + بدون receipt) | `scripts/reaper.py` |
| `superseded` | تسک جدیدی جایگزین شد | Orchestrator، با اشاره به جانشین |

```json
{
  "schema_version": "2.0.0",
  "task_id": "T-0142",
  "status": "complete",
  "agent": "config-engineer",
  "agent_lineage": "opus5/config-engineer@2",
  "autonomy_level": "L2",
  "autonomy_shadow": {"would_have_used": "L3", "decision_hash": "sha256:aa71...",
                      "agreed_with_human": true},
  "workstream": "agentic-core",
  "prev_receipt_hash": "sha256:9f2c8b17d0e4a5f3c2b1908877665544332211aabbccddeeff0011223344556677",
  "receipt_hash": "sha256:1c4e5a...",
  "chain_index": 142,
  "started_at": "2026-07-28T11:41:02Z",
  "completed_at": "2026-07-28T11:58:41Z",
  "intent": "انتشار profile reality-v7 روی canary 1%",
  "why_one_sentence": "CSR مسیر IR-A سه روز پیاپی زیر SLO بود و profile v7 در sim آن را ۱.۹ واحد بهبود داد.",
  "inputs_hash": "sha256:4b1d...",
  "idempotency": {"class": "forever", "key": "sha256:7ac2...",
                  "components": ["cap","artifact_hash","target_epoch"]},
  "input_provenance": [
    {"field": "$.artifact", "source": "repo:configs/profiles/reality-v7.yaml",
     "trust": "internal", "sanitizer": null, "content_hash": "sha256:8de1..."}
  ],
  "transport": "T1",
  "changes": [{"path": "configs/profiles/reality-v7.yaml", "commit": "abc1234",
               "diff_stat": "+42-3"}],
  "sim_evidence": {"scenarios": ["config_canary_regression", "node_outage"],
                   "seeds": [11, 27, 43], "result": "pass",
                   "report": "artifacts/sim/T-0142/report.json"},
  "verification": [
    {"check": "qa-gate", "result": "pass", "evidence": "artifacts/qa/T-0142.json",
     "verifier": "qa-gate", "independent_of_author": true},
    {"check": "canary-probe", "result": "pass", "evidence": "artifacts/probe/T-0142.json",
     "metric": {"csr": 0.991}, "n": 1418, "n_min": 1200,
     "stat_test": "always-valid-p", "p_value": 0.011, "conclusive": true,
     "probe_fleet": ["asn:AS1", "asn:AS2", "asn:AS3"]}
  ],
  "policy_decisions": [{"rule": "cfg.publish.canary", "decision": "allow",
                        "reason": "n>=n_min، error budget موجود، taint=internal"}],
  "cost": {"tokens_in": 31200, "tokens_out": 10000, "usd": 0.62, "wall_clock_s": 1059,
           "model_usage": [{"model": "claude-opus-5", "step": "DECIDE", "tokens": 18400},
                           {"model": "cheap-tier", "step": "SENSE", "tokens": 22800}],
           "budget_reservation_id": "BR-2026-07-28-0091"},
  "rollback": {"method": "git revert abc1234 + profile pin reality-v6",
               "tested": true, "tested_at": "2026-07-28T11:52:10Z",
               "tested_in": "sim", "max_ttr_s": 240},
  "handoff_note": "canary روی ۱٪ سبز؛ گام بعدی ارتقا به ۱۰٪ پس از پنجرهٔ ۳۰ دقیقه.",
  "control_room_task": "moxt://workflow/control-room/T-0142",
  "clickup_task": null
}
```

قواعد سخت:
*   **زنجیره:** `prev_receipt_hash` = هش receipt قبلی **همان workstream**. `receipt_hash` = `sha256` از بدنهٔ receipt با فیلد `receipt_hash` خالی. `scripts/verify.py --chain` در هر PR و nightly زنجیرهٔ همهٔ workstreamها را از ریشه بازبینی می‌کند. شکست زنجیره = incident امنیتی، نه یک خطای CI.
*   بازنویسی receipt گذشته ممنوع است؛ اصلاح فقط با receipt جدید `superseded` و اشاره به قبلی.
*   `status: crashed` را فقط reaper می‌نویسد و باید شامل `lease_evidence` و آخرین event مشاهده‌شدهٔ آن actor باشد.
*   `rollback.tested: true` بدون `tested_at` و `tested_in` نامعتبر است. rollback تست‌نشده = rollback موجود نیست.
*   `sim_evidence` برای هر تغییر کدی/کانفیگی اجباری است (I11). `seed` ثبت‌شده تضمین می‌کند هر شکست دقیقاً بازتولیدشدنی است.

## ۳.۴) Agent Card

```yaml
id: lifecycle-growth
name: Lifecycle Growth Agent
version: 2.0.0
tier: 2
lineage: opus5/lifecycle-growth@1        # تبار prompt — مبنای استقلال two-key
model_default: cheap-tier
model_for: {decide: claude-opus-5, review: claude-opus-5, sense: cheap-tier}
owns: [growth/journeys/**, growth/campaigns/**]     # یک نویسنده per path (I17)
capabilities: [journey.design, campaign.draft, campaign.launch, suppression.manage]
inputs: [analytics.funnel, product.usage, support.tickets]
outputs: [campaign.artifact, journey.spec, lifecycle.report]
transports: {preferred: T2, fallback: T1, forbidden: []}
autonomy: {default: L2, campaign.launch: L1, suppression.manage: L3, max: L3}
idempotency:
  campaign.launch:    {class: forever, key: [cap, artifact_hash, target_epoch]}
  journey.design:     {class: scoped,  ttl: 60m, key: [from, to, cap, inputs_hash, env_epoch]}
  suppression.manage: {class: forever, key: [cap, list_hash, target_epoch]}
  analytics.funnel:   {class: none,    cache_ttl: 60s}
taint_policy:
  untrusted_inputs: [support.tickets]
  max_autonomy_when_untrusted: L1        # I16 — بدون استثنا
budget: {tokens_per_day: 300000, usd_per_day: 8, campaign_spend_cap_usd: 200,
         reserve_before_execute: true}
kpi:         [activation_rate, trial_to_paid, nrr]
counter_kpi: [unsubscribe_rate, support_contact_per_user, refund_rate]
counter_kpi_owner: trust-compliance      # مالک متفاوت — اجبار در CI (I13)
forbidden: [pricing_change, refund_issue, raw_pii_access, ad_spend_above_cap,
            self_approval, writing_outside_owns]
escalation: {to: orchestrator, on: [guardrail_breach, budget_80pct, policy_deny,
                                    counter_kpi_regression, degraded_sense]}
dependencies: [content-creative, cro-experiment, revenue-intelligence]
reviewed_by: adversarial-reviewer        # کلید دوم برای مسیرهای بحرانی
standby_for: crm-retention               # جانشینی ایجنت (§۱۱.۲)
standby_autonomy_penalty: 1              # جانشین یک سطح پایین‌تر کار می‌کند
heartbeat_sla_min: 15
sim_scenarios_required: [campaign_stop_loss, metric_gaming, prompt_injection]
```

هیچ ایجنتی بدون Agent Card معتبر فعال نمی‌شود. CI کارت را رد می‌کند اگر: `counter_kpi` خالی باشد، `counter_kpi_owner == id` باشد، `owns` با `owns` ایجنت دیگری تداخل داشته باشد، `idempotency` برای یک capability جهش‌دهنده تعریف نشده باشد، یا `sim_scenarios_required` خالی باشد.

## ۳.۵) A2A Task Envelope
یک envelope مشترک برای هر سه transport — جابه‌جایی بین T1/T2/T3 نباید هیچ تغییری در محتوا بخواهد.

```json
{
  "schema_version": "2.0.0",
  "task_id": "A2A-01K1G8B2C3D4E5F6G7H8J9K0M1",
  "created_at": "2026-07-28T11:40:00Z",
  "from": "orchestrator",
  "to": "qa-gate",
  "capability": "qa.gate.run",
  "transport": "T1",
  "idempotency": {
    "class": "scoped",
    "ttl_s": 900,
    "components": ["from", "to", "capability", "inputs_hash", "env_epoch"],
    "key": "sha256:5f0b9c...",
    "env_epoch": "2026-07-28T11:30:00Z",
    "target_epoch": null,
    "attempt": 1,
    "retry_of": null
  },
  "input": {
    "$schema": "analytics/schemas/qa.gate.run.input.json",
    "artifact": "configs/profiles/reality-v7.yaml",
    "ticket_excerpt": "<<UNTRUSTED_DATA source=support:zendesk#8123 >>\nکاربر می‌گوید اتصال قطع می‌شود\n<<END>>"
  },
  "input_provenance": [
    {"field": "$.input.artifact", "source": "repo:configs/profiles/reality-v7.yaml",
     "trust": "internal", "sanitizer": null, "content_hash": "sha256:8de1..."},
    {"field": "$.input.ticket_excerpt", "source": "support:zendesk#8123",
     "trust": "untrusted", "sanitizer": "envelope-v1", "content_hash": "sha256:c7a4..."}
  ],
  "capability_grant": {
    "granted_by": "policy-engine",
    "scope": ["qa.gate.run", "artifacts.read"],
    "max_autonomy": "L1",
    "reason": "taint=untrusted در $.input.ticket_excerpt → سقف L1 (I16)",
    "expires_at": "2026-07-28T12:40:00Z",
    "signature": "ed25519:9a3f..."
  },
  "deadline": "2026-07-28T13:00:00Z",
  "priority": "high",
  "correlation_id": "01K1G7T0000000000000000000",
  "causation_id": "01K1G7Y1M2P3Q4R5S6T7U8V9W0",
  "callback": {"T1": "state/a2a/outbox/orchestrator/", "T2": "moxt://task/T-0142",
               "T3": null},
  "autonomy_requested": "L2",
  "budget": {"tokens": 50000, "usd": 0.9, "reservation_id": "BR-2026-07-28-0091"},
  "world": "prod",
  "seed": null,
  "trace_id": "0af7651916cd43dd8448eb211c80319c"
}
```

**سه کلاس idempotency (اجباری، به‌ازای هر capability در Agent Card):**

| class | کاربرد | کلید | رفتار |
| ---| ---| ---| --- |
| `forever` | عملیات جهش‌دهنده و غیرقابل‌تکرار: deploy، پرداخت، provision | `[cap, artifact_hash, target_epoch]` | تکرار با همان کلید = بازگشت نتیجهٔ قبلی، بدون اجرا. انتشار مجدد آگاهانه با `target_epoch` جدید. |
| `scoped` | نتیجه در پنجرهٔ TTL معتبر است: qa gate، probe، تحلیل | `[from, to, cap, inputs_hash, env_epoch]` | بعد از TTL، اجرای مجدد. `env_epoch` تغییر محیط را در کلید می‌آورد. |
| `none` | خواندنی: query متریک، funnel | — | هرگز idempotency ماندگار؛ فقط cache کوتاه (`cache_ttl`). |

قانون سخت: کلید idempotency **بدون بعد زمان** ممنوع است. یک SENSE کهنه بدتر از SENSE گران است — سیستمی که ورودی کهنه می‌خواند کور است و کورکورانه تصمیم می‌گیرد. `retry_of` + `attempt` تلاش مشروع پس از شکست گذرا را از تکرار ناخواسته تفکیک می‌کند.

قانون taint: `input_provenance` برای **هر** فیلد ورودی که از خارج repo آمده اجباری است. اگر پارامتر یک ابزار جهش‌دهنده از فیلدی با `trust: untrusted` مشتق شده باشد، `capability_grant.max_autonomy` حداکثر `L1` است — بدون استثنا، بدون override، بدون «مورد خاص».

## ۳.۶) Lease

```json
{
  "schema_version": "2.0.0",
  "workstream": "agentic-core",
  "holder": "agent:config-engineer",
  "holder_lineage": "opus5/config-engineer@2",
  "session": "S-91",
  "acquired_at": "2026-07-28T11:40:00Z",
  "ttl_min": 90,
  "expires_at": "2026-07-28T13:10:00Z",
  "heartbeat_at": "2026-07-28T11:59:40Z",
  "heartbeat_interval_min": 15,
  "missed_heartbeats": 0,
  "fencing_token": 42,
  "owns_paths": ["configs/**", "state/events/2026-07-28/config-engineer.ndjson"],
  "reaped_by": null,
  "reap_reason": null
}
```

قواعد:
*   **fencing:** هر write به state باید `fencing_token >= current` را ثابت کند، وگرنه reject. این تنها محافظ واقعی در برابر split-brain است. token با هر acquire یکنوا افزایش می‌یابد و هرگز بازیافت نمی‌شود.
*   **fail-closed:** اگر lease قابل تأیید نباشد (فایل ناخوانا، ساعت مشکوک، token عقب‌تر) → نوشتن ممنوع، نه «فرض کن مجاز است».
*   **reaper:** `scripts/reaper.py` در workflow `heartbeat` هر ۱۵ دقیقه lease منقضی یا سه‌بار heartbeat‌گم‌کرده را باطل می‌کند، `fencing_token` را جلو می‌برد، receipt `crashed` می‌نویسد و رویداد `lease.reaped` می‌زند.
*   `owns_paths` با `owns` در Agent Card باید سازگار باشد؛ ناسازگاری = رد lease.

## ۳.۷) تکامل schema و مهاجرت (upcaster)
event sourcing بدون upcaster پس از اولین breaking change قابلیت replay را از دست می‌دهد — یعنی همان چیزی که کل ارزش event sourcing است.

```plain
analytics/schemas/migrations/
├─ v1_0__v1_1.py     def upcast(event: dict) -> dict   # تابع خالص، بدون I/O
├─ v1_1__v2_0.py
└─ registry.py       زنجیرهٔ نسخه‌ها + resolve(version) -> [upcasters]
```

قواعد اجباری:
*   خواننده باید **همهٔ** نسخه‌های تاریخی را بخواند؛ upcasterها به‌ترتیب اعمال می‌شوند تا نسخهٔ جاری.
*   upcaster تابع خالص است: بدون شبکه، بدون فایل، بدون ساعت. تست round-trip روی نمونه‌های واقعی `state/archive/`.
*   compaction هرگز event خام را بازنویسی نمی‌کند؛ فقط snapshot جدید می‌سازد.
*   CI روی حذف یا تغییر معنای فیلد **بدون** upcaster شکست می‌خورد (I18).
*   همین مکانیزم برای Receipt و Agent Card نیز اعمال می‌شود؛ receipt قدیمی باید در زنجیره قابل‌بازبینی بماند.

* * *
# ۴) Ports & Adapters (قفل نشدن به vendor)
هر Adapter این interface را پیاده کند (Python Protocol / TS interface):

```python
class Adapter(Protocol):
    name: str
    world: Literal["prod", "sim"]
    def healthz(self) -> Health: ...
    def capabilities(self) -> list[str]: ...
    def execute(self, op: str, payload: dict, *,
                idem_key: str, idem_class: Literal["forever","scoped","none"],
                dry_run: bool, deadline: datetime,
                provenance: list[Provenance]) -> Result: ...
    def rollback(self, receipt_ref: str) -> Result: ...
```

الزامات مشترک همهٔ Adapterها: idempotency طبق کلاس اعلام‌شده · exponential backoff با jitter · circuit breaker (۵ خطای پیاپی → open برای ۶۰ ثانیه) · timeout سخت · redaction روی log · `dry_run` واقعی (نه no-op) · contract test مستقل · **یک fake متناظر در `sim/fakes/` که همان contract test را پاس کند**. Adapter بدون fake، merge نمی‌شود — چون بدون آن سناریوهای §۱۶ اجرا نمی‌شوند.

| Adapter | Ops حداقلی |
| ---| --- |
| github | commit\_atomic, read\_state, append\_event, create\_pr, dispatch\_workflow, read\_repo\_var |
| moxt | upsert\_task, assign\_agent, set\_status, set\_field, read\_approval, read\_killswitch\_task |
| clickup | upsert\_task, comment, set\_status, set\_custom\_field, read\_approval *(اختیاری، پشت flag)* |
| marzneshin | list\_nodes, publish\_config, probe, rollback\_profile, user\_provision |
| payments | create\_checkout, verify\_webhook, reconcile, refund (L1 only) |
| analytics | ingest\_event, query\_metric, cohort, experiment\_readout, sample\_size |
| messaging | send\_campaign, suppression\_add, quiet\_hours\_check, out\_of\_band\_alert |
| observability | push\_metric, query\_slo, fire\_alert, error\_budget |
| vault | get\_secret (short-lived), rotate, audit |

`messaging.out_of_band_alert` یک hard requirement است، نه یک قابلیت جانبی: اگر GitHub و Moxt هر دو در دسترس نباشند، Owner هیچ راهی برای شنیدن هشدار ندارد (§۱۱.۲).

* * *
# ۵) لایهٔ Transport — سه مسیر با تنزل تدریجی
**اصل حاکم:** L3 یک قرارداد است، نه یک سرویس. هیچ SPOF ای در مسیر کنترل مجاز نیست. Gateway باید بتواند بمیرد و سیستم با **تنزل latency**، نه توقف، ادامه دهد.

## ۵.۱) T1 — git-transport (baseline، همیشه کار می‌کند)

```plain
task    = یک فایل JSON (envelope §۳.۵) در state/a2a/inbox/{agent}/{ulid}.json + commit atomic
trigger = GitHub Actions: repository_dispatch یا push با path filter روی state/a2a/inbox/**
                          (workflow: a2a-dispatch.yml) — یا Moxt cron به‌عنوان کف امنیتی
result  = state/a2a/outbox/{from}/{ulid}.json → سپس processed/ با اشاره به receipt
latency ~۳۰–۹۰ ثانیه · durability عالی · audit رایگان و ذاتی · هزینهٔ زیرساخت صفر
```

قواعد: مسیر inbox هر ایجنت فقط توسط dispatcher نوشته می‌شود و فقط توسط خود ایجنت خوانده/منتقل می‌شود (I17) · هیچ فایلی در `inbox/` حذف نمی‌شود، فقط به `processed/` منتقل می‌شود · idempotency روی نام فایل (ULID) + کلید envelope هر دو بررسی می‌شود.

## ۵.۲) T2 — moxt-transport (fast path بومی، بدون host خارجی)

```plain
task    = یک Task در Moxt Workflow با envelope در بدنه؛ assign به AI Teammate آن ایجنت
trigger = خودِ assign — pipeline ایجنت مقصد بومی راه می‌افتد
result  = تغییر status + کامنت با اشاره به receipt در GitHub
latency ~ثانیه · بدون سرور · صف، مالکیت، وضعیت، تاریخچه و مسیر تأیید انسانی بومی
```

بینش معماری: در Moxt، «assign کردن یک Task به یک AI Teammate» *خودش* یک A2A dispatch bus است. بنابراین VS-3 بدون نوشتن حتی یک خط FastAPI تحویل‌شدنی است.

## ۵.۳) T3 — http-transport (اختیاری، فقط برای مقیاس — VS-12)
**Stack:** FastAPI + Pydantic v2 + Postgres (tasks/audit) + Redis (rate limit, idempotency cache) + mTLS یا OIDC. **نقش: کش و بهینه‌سازی latency، نه منبع حقیقت.**

| Method | Path | رفتار |
| ---| ---| --- |
| GET | `/.well-known/agent-card.json` | کارت ایجنت میزبان |
| GET | `/healthz` `/readyz` | liveness/readiness |
| GET | `/v1/agents` | Registry، فیلتر بر capability |
| POST | `/v1/tasks` | ایجاد task، `202` + `task_id`؛ idempotent طبق کلاس اعلام‌شده |
| GET | `/v1/tasks/{id}` | وضعیت + آخرین state |
| POST | `/v1/tasks/{id}/messages` | پیام میان‌مرحله‌ای |
| POST | `/v1/tasks/{id}/cancel` | لغو با دلیل، rollback خودکار در صورت نیاز |
| GET | `/v1/tasks/{id}/events` | SSE stream |
| POST/GET | `/v1/artifacts[/{id}]` | آپلود/دریافت artifact با hash |
| POST | `/v1/policy/evaluate` | dry-run تصمیم policy |
| GET | `/v1/killswitch` | **فقط خواندن.** فعال‌سازی هرگز انحصاراً از اینجا نیست (I14) |

## ۵.۴) State machine هر Task (مشترک بین سه transport)

```plain
created → admitted → queued → running → (awaiting_approval) → verifying
        → completed | failed | cancelled | rolled_back | crashed
```

هر گذار یک event تولید می‌کند. `awaiting_approval` فقط برای L0/L1؛ timeout آن ۲۴ ساعت → auto-cancel + notify + receipt `abandoned`. گذار به `crashed` را فقط reaper می‌نویسد.

## ۵.۵) انتخاب مسیر، health و fallback

```plain
health check هر ۶۰ ثانیه روی هر transport فعال
۳ خطای پیاپی روی مسیر پیش‌فرض → fallback خودکار به T1 + رویداد transport.degraded
بازگشت به مسیر سریع‌تر: ۵ health check سبز پیاپی (hysteresis، برای جلوگیری از flapping)
انتخاب پیش‌فرض: transports.preferred در Agent Card، مشروط به سلامت
```

**قانون سخت (I14):** هیچ قابلیت ایمنی‌ای — kill switch، lease، budget، receipt، audit — نباید فقط روی T3 زنده باشد. contract testهای ایمنی با T3 خاموش اجرا می‌شوند.

## ۵.۶) الزامات سخت هر transport
احراز هویت (T1: امضای commit و OIDC · T2: هویت workspace · T3: mTLS/OIDC با scope per-capability) · replay protection (nonce + پنجرهٔ ۵ دقیقه؛ در T1 با ULID + idempotency key) · rate limit per agent per capability · schema validation ورودی **و** خروجی · redaction قبل از persist · audit log جدا و append-only · backpressure (T1: طول صف inbox · T3: queue depth و 429) · deadline propagation · `trace_id` در همهٔ لاگ‌ها (OpenTelemetry).

## ۵.۷) خط لولهٔ Config — canary یک experiment است
«canary سبز» بدون قدرت آماری، نویز است. یک موتور آماری، دو کاربرد (canary و experiment).

```plain
مراحل: 1% → 10% → 50% → 100%
gate ارتقا در هر مرحله:
  n ≥ n_min   (n_min از MDE محاسبه می‌شود؛ power 0.8، alpha 0.05)
  sequential test با always-valid p-value → توقف زودهنگام ایمن مجاز
  error budget موجود (§۱۴)
  probe fleet سالم
خروجی ممکن: promote | hold | rollback | inconclusive
اگر n < n_min → inconclusive → ماندن در همان مرحله. «داده کافی نیست» هرگز «سبز» نیست.
```

**مشخصات ناوگان probe (اجباری):** حداقل ۳ شبکهٔ مستقل با ASN متفاوت · فاصلهٔ نمونه‌گیری ثابت و اعلام‌شده · مسیر گزارش مستقل از مسیر کنترل · **fail-closed:** بدون حداقل ۲ probe سالم، هر ارتقا ممنوع است و مرحله در `hold` می‌ماند. rollback خودکار در صورت افت CSR زیر آستانه با p-value معتبر، با `max_ttr_s` اعلام‌شده در receipt.

* * *
# ۶) Policy Engine و سطوح استقلال
پیاده‌سازی: OPA/Rego یا موتور داخلی declarative در `agents/policies/rules.yaml`. تصمیم‌ها همیشه `allow | allow_with_conditions | require_approval | deny` و همیشه با `reason` قابل‌خواندن که در receipt ثبت می‌شود. Policy Engine روی هر سه transport یکسان اجرا می‌شود و در T1 به‌صورت یک گام اجباری در `a2a-dispatch.yml` است.

## ۶.۱) ماتریس ریسک → سطح استقلال

| کلاس عملیات | نمونه | سطح | Guardrail اجباری |
| ---| ---| ---| --- |
| Read/Analyze | خواندن metric، تحلیل funnel | L4 | rate limit |
| Internal artifact | نوشتن doc، ADR، backlog | L3 | receipt |
| Reversible config | feature flag، suppression list | L3 | rollback tested + auto-revert on SLO breach |
| Canary publish | انتشار profile روی ۱٪ | L2 | QA gate + probe fleet + `n ≥ n_min` + auto-rollback |
| Full rollout | ۱۰۰٪ کاربران | L2 | canary سبز ۳۰ دقیقه **و** آماری قطعی + error budget موجود |
| Infra mutate | node جدید، terraform apply | L1 | plan diff + Owner approve |
| Money out | ad spend, refund, payout | L1 | budget cap + reservation + Owner approve |
| Pricing/Contract | تغییر قیمت، ToS | L0 | فقط پیشنهاد |
| Security-sensitive | rotation، IAM، secret | L1 | ۴ چشم (Security Agent + Adversarial Reviewer یا Owner) |
| **هر عملیات با ورودی `untrusted`** | ایجنت پشتیبانی روی متن تیکت | **حداکثر L1** | taint enforcer §۱۵.۲، بدون استثنا |

## ۶.۲) ارتقای خودکار استقلال (Autonomy Ratchet + Shadow Mode)
این قابلیت را حتماً بساز؛ همین است که سیستم را واقعاً autonomous می‌کند. اما «۳۰ اجرای موفق در L1» چیزی دربارهٔ رفتار سیستم **بدون** انسان ثابت نمی‌کند — پس شواهد counterfactual لازم است:

```plain
Shadow Mode: ایجنت در سطح L(n) کار می‌کند و هم‌زمان تصمیمی که در L(n+1)
             می‌گرفت را ثبت می‌کند (بدون اجرا) → receipt.autonomy_shadow

شرایط ارتقا از Ln به Ln+1 (همهٔ سه شرط، AND):
  1. ۳۰ اجرای متوالی: 0 rollback، 0 guardrail breach، ۱۰۰٪ receipt کامل،
     انحراف KPI < 2%، و هیچ رگرسیون counter-KPI
  2. ≥۹۵٪ توافق میان تصمیم سایه و تصمیم تأییدشدهٔ انسان، در ≥۲۰ نمونه
  3. سبز بودن همهٔ sim_scenarios_required آن ایجنت با ≥۳ seed تازه

سقف: حداکثر تا max در Agent Card؛ هرگز بالاتر از L1 برای money/security/infra.
هر breach → تنزل فوری یک سطح + قرنطینهٔ ۷۲ ساعته + سناریوی رگرسیون جدید در sim/.
```

قرارداد خروجی `/autonomy-review` (اجباری، ماشین‌خوان): برای هر (agent, capability) → `current_level`, `evidence_window`, `clean_runs`, `shadow_agreement`, `shadow_n`, `sim_status`, `verdict ∈ {promote, hold, demote}`, `reason`. خروجی به `state/a2a/inbox/orchestrator/` نوشته می‌شود، نه فقط چاپ.

## ۶.۳) Kill Switch — چندمسیره و fail-closed
مکانیزم توقف اضطراری هرگز نباید روی یک SaaS خارجی یا یک token قابل‌انقضا سوار باشد.

```plain
مسیرهای فعال‌سازی (OR — هر کدام کافی است):
  K1  فایل state/KILL در repo (منبع اصلی، atomic، نسخه‌دار، بدون شبکه قابل خواندن)
  K2  GitHub repository variable KILL_SWITCH=global|scoped:{agent|capability}|budget
  K3  وضعیت Task در Moxt Workflow «Control Room / Kill Switch»
  K4  CLI: scripts/killswitch.py (مسیر محلی، بدون شبکه)
  K5  خودکار توسط Orchestrator: نقض SLO بحرانی · هزینه > ۳× baseline ·
      الگوی خطای غیرعادی · هشدار امنیتی · گم شدن ۳ heartbeat پیاپی

سه دامنه: global (همه‌چیز متوقف، فقط read) · scoped:{agent|capability} · budget

قانون fail-closed (اجباری):
  اگر یک worker نتواند وضعیت kill switch را از حداقل یک مسیر معتبر
  با timestamp تازه‌تر از ۱۵ دقیقه بخواند
  → همهٔ عملیات با blast radius > L3 متوقف می‌شود (halt، نه continue)
  → رویداد killswitch.unreadable + fail_closed_engaged=true در STATE
  «نمی‌دانم» هم‌ارز «متوقف شو» است، نه هم‌ارز «مجاز است».

غیرفعال‌سازی: همیشه انسانی (Owner)، همیشه با ADR، هرگز خودکار.
```

همین اصل fail-closed در سه جای دیگر هم اعمال می‌شود: probe سالم موجود نیست → ارتقای canary ممنوع · budget ledger خوانده نمی‌شود → فقط عملیات L4 · lease قابل تأیید نیست → نوشتن ممنوع.

`scripts/killswitch.py --verify` هر شبانه در CI اجرا می‌شود و **عملاً** هر ۵ مسیر را تست می‌کند (فعال‌سازی در محیط sim، تأیید توقف، غیرفعال‌سازی، ثبت receipt). **kill switch تست‌نشده = kill switch وجود ندارد.**

## ۶.۴) مدل هزینه، بودجه و tick تطبیقی
سقف بدون مدل هزینه بی‌معناست. ۱۹ ایجنت × ۳۰۰k توکن = ۵.۷M توکن در روز؛ هیچ سقف دلاری ثابتی این را پوشش نمی‌دهد مگر مدل هزینه صریح باشد.

**دفتر بودجهٔ سلسله‌مراتبی** (`state/budget/ledger.json`): `workspace → tier → agent → task`. رزرو **قبل** از اجرا (`reservation_id` در envelope و receipt)، تسویه بعد از اجرا با مصرف واقعی. سقف سطح tier سخت‌گیرانه‌تر از جمع سقف‌های agent است (over-subscription کنترل‌شده). رزرو ناموفق = تسک queue می‌شود، نه اینکه بدون بودجه اجرا شود.

**مسیریابی مدل بر اساس نوع کار:** classify/extract/SENSE با مدل ارزان · مدل رده‌بالا فقط برای DECIDE، طراحی، و بازبینی خصمانه. `model_usage` در هر receipt ثبت می‌شود تا `agent_leverage` قابل اندازه‌گیری باشد.

**tick تطبیقی، رویدادمحور:**

```plain
trigger اصلی = رویداد واقعی (webhook، alert، تغییر متریک بیش از آستانه)
polling فقط کف امنیتی: ۳۰ دقیقه در حالت فعال
  → backoff نمایی تا ۴ ساعت وقتی N tick پیاپی «تغییر معنادار» نداشتند
دروازهٔ ارزان: یک SENSE سبک (فقط هش مجموعهٔ متریک‌ها) تصمیم می‌گیرد
  آیا tick گران اجرا شود یا نه
```

**`budget_forecast`:** پیش‌بینی مصرف پایان روز در هر tick. ۸۰٪ → escalate به Orchestrator + کاهش موازی‌سازی. ۱۰۰٪ → kill switch از نوع `budget` (خودکار، K5).

* * *
# ۷) لایهٔ Claude Code
## ۷.۱) CLAUDE.md (حداکثر ۴۰۰ خط)
فقط قوانین پایدار: SSoT، چرخهٔ FSP، مالکیت مسیرها (CODEOWNERS mirror)، DoD، دستورهای تست، سیاست secret، سبک کد، ممنوعیت‌ها، قانون «sim قبل از prod»، و قانون fail-closed. دانش سنگین و متغیر → Skills و Context Pack. زبان: فارسی برای قواعد، انگلیسی برای شناسه‌ها و دستورها (D10).

## ۷.۲) Hooks (قطعی، با exit code، دو ردهٔ زمانی)
یک بودجهٔ ۳ ثانیه‌ای با «اجرای مجموعهٔ تست» جمع نمی‌شود. پس hookها دو رده دارند:

**رده A — < ۳ ثانیه، محلی، blocking، بدون شبکه:**

| Hook | ورودی | شکست (exit≠0) وقتی |
| ---| ---| --- |
| SessionStart | session meta | STATE کهنه‌تر از ۲۴ ساعت و sync ناموفق · kill switch ناخوانا (fail-closed) |
| PreToolUse | tool + args | lease نامعتبر یا fencing عقب‌تر · نوشتن خارج از `owns` · secret در args · capability بدون scope امضاشده · پارامتر مشتق از `untrusted` با autonomy > L1 |
| PostToolUse | tool result | schema invalid · secret در خروجی · format شکست · `redaction_map` ناقص |
| PreCommit | staged diff | نبود task ID · CODEOWNERS نقض · gitleaks روی **staged diff** · فیلدهای receipt ناقص · شکست زنجیرهٔ receipt · schema فایل‌های تغییریافته |
| TaskCompleted | task | receipt وجود ندارد · `status` نامعتبر · evidence نبود · `rollback.tested != true` · `sim_evidence` غایب برای تغییر کدی |
| Stop | session | HANDOFF ننوشته · lease آزاد نشده · event پایانی ثبت نشده |

**رده B — < ۹۰ ثانیه، pre-push یا CI:** مجموعهٔ تست کامل · contract test همهٔ Adapterها · سناریوهای `sim/` مرتبط · SAST · policy test · `verify.py --chain`.

قواعد: هر hook خروجی JSON می‌دهد و خودش event ثبت می‌کند · **هیچ hook ای I/O شبکه ندارد** (دلیل شمارهٔ یک flakiness) · hook هرگز «مشکوک اما اجازه بده» برنمی‌گرداند؛ در ابهام exit≠0.

## ۷.۳) Skills
هر `SKILL.md` این هدر اجباری را دارد: `name, when_to_load, inputs, outputs, preconditions, policy_refs, steps, tests, evidence, rollback, sim_scenarios, owner_agent`. Skill بدون تست و بدون سناریوی sim، merge نمی‌شود. Skillها فقط on-demand load می‌شوند (Context Efficiency یک KPI است و در STATE ثبت می‌شود).

## ۷.۴) MCP
هر MCP server: allowlist ابزار · timeout · rate limit · read-only پیش‌فرض · write فقط با scope صریح و امضاشده · audit کامل. هرگز credential بلندعمر؛ token کوتاه‌عمر از Vault. خروجی هر MCP به‌عنوان داده با `trust` مناسب برچسب می‌خورد (§۱۵.۲) — خروجی MCP هرگز دستور نیست.

## ۷.۵) Plugin commands
`/fsp-start` `/growth-plan` `/campaign` `/experiment` `/qa-gate` `/handoff` `/incident` `/succession` `/killswitch` `/autonomy-review` `/sim` `/adversarial-review`

هر command یک قرارداد خروجی ماشین‌خوان دارد که در `plugins/marzneshin-ops/` schema شده است. command بدون schema خروجی = command ناقص.

* * *
# ۸) CI/CD (GitHub Actions)

| Workflow | Trigger | وظیفه |
| ---| ---| --- |
| validate | PR + push | schema validation، lint، unit، contract test، receipt lint، `verify.py --chain`، سناریوهای sim مرتبط |
| security | PR + nightly | gitleaks، SCA، SAST، dependency review، policy test، injection suite |
| compact | hourly | فشرده‌سازی event → STATE.json + archive + بررسی شکاف `actor_seq` |
| a2a-dispatch | push روی `state/a2a/inbox/**` + repository_dispatch | مسیر T1: policy evaluate → assign → اجرا → outbox |
| release | tag | build، canary gate آماری، progressive rollout، auto-rollback |
| mirror | daily | mirror به remote دوم + cold clone artifact + بستهٔ RECOVERY |
| heartbeat | \*/15m | بررسی lease منقضی، dead agent detection، auto-release، reaper، خواندن kill switch |
| succession | on lease-expiry / member-removed | اجرای پروتکل §۱۱.۱ |
| experiment | \*/30m | guardrail check، auto-stop، readout، SRM check |
| sim-nightly | nightly | کل مجموعهٔ سناریو با ۱۰ seed تصادفی + `killswitch.py --verify` + امتیازدهی |
| notify | on events | mirror به Control Room + کانال هشدار + out-of-band در سطح critical |

OIDC برای احراز هویت Actions؛ هیچ secret بلندعمری در repo. `main` protected، CODEOWNERS اجباری (چهار مسیر انسانی + مالک ایجنتی برای بقیه)، signed commits.

* * *
# ۹) Control Room (Moxt Workflow اصلی، ClickUp اختیاری)
**اصل کلیدی:** Control Room سطح **کار و کنترل** است، نه منبع حقیقت (I1). GitHub تنها SSoT می‌ماند. Control Room اولیه بومی Moxt است تا مسیر Governance به هیچ SaaS پرداختی و هیچ token خارجی وابسته نباشد.

## ۹.۱) ساختار (Moxt Workflow — مسیر اصلی)

```plain
Workflows:
├─ Control Room     → Approvals · Incidents · Risks · Kill Switch
├─ Engineering      → Agentic Core · Product Reliability · Infra
├─ Growth & Revenue → Growth · Revenue · Experiments · Campaigns
├─ Security & Gov   → Security Reviews · ADRs · Compliance
└─ Knowledge        → MASTER-PLAN · BUILD-SPEC v2.0 · Runbooks · Agent Cards · RECOVERY
```

هر Task در Control Room دو نقش هم‌زمان دارد: mirror انسانی‌خوانِ وضعیت GitHub، و **trigger** ایجنت مقصد (T2). assign کردن Task = dispatch.

## ۹.۲) Custom Fields روی همهٔ Workflowهای اجرایی
`Owner (agent)` · `Autonomy Level` L0–L4 · `Trigger` · `Input Ref` · `Output Ref` · `KPI` · `Counter-KPI` · `Evidence` · `Receipt ID` · `Receipt Status` · `Rollback` · `Risk Class` · `Blast Radius` · `Budget (tokens/USD)` · `Reservation ID` · `Approval` · `Slice` · `Transport` · `Sim Evidence` · `Taint Level`.

## ۹.۳) Statuses
`Backlog → Claimed → In Progress → Awaiting Approval → Verifying → Done → Rolled Back` (+ `Blocked`، `Crashed`).

## ۹.۴) Views و Dashboard
Viewها: «Awaiting Approval» · «Autonomy > L2» · «Rolled Back» · «Lease منقضی» · «Guardrail breach» · «Receipt Status ≠ complete» · «Taint = untrusted».
Dashboard «Revenue Command Center» (VS-10، Mini App + Grafana): NSM · MRR/NRR · funnel · CAC/LTV · CSR/SLO · experiment readout · agent leverage · هزینهٔ توکن · counter-KPI panel.

## ۹.۵) Sync، دسترسی و ClickUp اختیاری
**Sync:** GitHub → Control Room خودکار از workflow `notify`. Control Room → GitHub **فقط** برای دو چیز: تغییر فیلد `Approval` و تغییر وضعیت Task مربوط به Kill Switch (K3). هیچ چیز دیگری معکوس sync نمی‌شود (I1).

**ClickUp (اختیاری):** پشت `adapters/clickup` با همان interface §۴، فعال با flag و token. اگر فعال شود، mirror فقط‌خواندنی است با همان دو استثنای بالا. ساختار معادل: یک Workspace مرکزی، اعضا به‌عنوان **Member** (نه Guest)، Space روی Public داخل Workspace، Docs روی `Can edit`. هرگز پروژه را در اکانت‌های جدا کپی نکن — تسک یکی است و mirror نمی‌شود.

**Notification:** هر عضو Watcher روی Workflow مربوطه + یک کانال برای رویدادهای خودکار + **کانال خارج از باند** برای رویدادهای critical (§۱۱.۲).

* * *
# ۱۰) تیم Super Agent — ۱۹ ایجنت، ترتیب ساخت اجباری
**ترتیب ساخت اجباری:** ابتدا **۷ ایجنت Tier 0** (کامل و سبز)، سپس Tier 1 پس از سبز شدن VS-5، و Tier 2 در فاز ۳. ساخت هر ۱۹ ایجنت از روز اول = هرج‌ومرج، نه اتوماسیون.

## ۱۰.۱) Tier 0 — عملیات حیاتی (۷ ایجنت)

| Agent | Owns | Autonomy | Trigger | KPI | Counter-KPI (مالک متفاوت) | Forbidden |
| ---| ---| ---| ---| ---| ---| --- |
| Orchestrator (CEO Agent) | routing، lease، budget ledger، escalation | L3 (L1 برای money/infra) | tick تطبیقی + هر رویداد escalation | agent leverage، intervention rate، tick cost | queue starvation، escalation latency *(adversarial-reviewer)* | اجرای مستقیم تغییر در data plane؛ تأیید کار خودش |
| Config Engineer | `configs/**` | L2 | تغییر profile، probe fail | CSR، time-to-publish | rollback rate، inconclusive canary rate *(qa-gate)* | rollout ۱۰۰٪ بدون canary آماری‌قطعی |
| InfraOps/SRE | `infra/**`، nodes | L1 | alert، capacity، chaos drill | uptime، P95، MTTR | change failure rate، cost per node *(security-compliance)* | terraform apply بدون plan approve |
| QA Gate | `qa/**`، test matrix، gate definitions | L3 | هر PR و هر release candidate | escaped defects، gate coverage | false-pass rate، gate flakiness *(adversarial-reviewer)* | تأیید خودش روی کار خودش؛ تغییر gate خودش بدون بازبینی خصمانه |
| Security & Compliance | `security/**`، policy، `security/compliance/**` | L1 | PR، nightly scan، حادثه | secret leaks=0، MTTD | مسدودسازی کاذب، معطلی PR امنیتی *(adversarial-reviewer)* | دور زدن ۴ چشم؛ تصمیم L0 (ToS/حوزهٔ قضایی) |
| **Handoff Guardian** | `state/HANDOFF.md`، lease، receipt coverage | L3 | پایان هر جلسه + heartbeat هر ۱۵ دقیقه | continuity score، receipt coverage ۱۰۰٪ | lease thrash، false reap rate *(orchestrator)* | بستن جلسه بدون HANDOFF؛ حذف lease زندهٔ سالم |
| **Adversarial Reviewer** | (بدون مالکیت مسیر — نقش برشی) | L3 برای رد، L0 برای تأیید | هر تغییر روی مسیر بحرانی، هر ارتقای autonomy، هر gate جدید QA | catch rate، rejection precision | over-rejection rate، review latency *(orchestrator)* | نوشتن کد production؛ تأیید تغییری که خودش پیشنهاد داده |

**Handoff Guardian در Tier 0 است**، چون بدون آن قانون آهنین ۳ («هیچ جلسه‌ای بدون HANDOFF») از روز اول قابل اجبار نیست. lease زامبی را آزاد می‌کند، reaper را می‌راند و `continuity_score` را می‌سازد.

**Adversarial Reviewer** یک نقش برشی است: تبار مستقل (مدل یا prompt-lineage متفاوت)، دسترسی به **شواهد خام** نه خروجی ایجنت اول، و وظیفهٔ صریح **رد کردن**. این کلید دومِ two-key است و بازبین gateهای QA (چون «چه کسی gate را بازبینی می‌کند» یک سؤال بی‌پاسخ نمی‌ماند).

## ۱۰.۲) Tier 1 — تاب‌آوری و دانش (۴ ایجنت)

| Agent | Owns | Autonomy | Trigger | KPI | Counter-KPI | Forbidden |
| ---| ---| ---| ---| ---| ---| --- |
| Recon | `growth/personas`، محیط/provider watch | L3 | nightly + تغییر provider | detection lead time | false alarm rate *(orchestrator)* | تغییر config بر اساس یافتهٔ تأییدنشده |
| Panel Automation | `adapters/marzneshin` | L2 | تغییر پنل، provision backlog | provisioning time | provision error rate *(qa-gate)* | دسترسی به PII خام |
| Docs & Knowledge | `CONTEXT-PACK.md`، Runbooks، ADR index | L3 | هر ADR، هر incident، هفتگی | knowledge concentration، context efficiency | doc drift، سند بی‌استفاده *(handoff-guardian)* | تغییر BUILD-SPEC بدون ADR |
| **Analytics Engineer** | `analytics/**` (events، schemas، models، migrations) | L2 | تغییر taxonomy، افت کیفیت داده | data freshness، schema conformance | metric drift، event loss rate *(adversarial-reviewer)* | تغییر تعریف NSM بدون ADR؛ حذف فیلد بدون upcaster |

**Analytics Engineer** پیش‌نیاز VS-8/VS-10 است: کل event taxonomy، JSON Schemaها، upcasterها و مدل‌های unit-economics مالک مشخص می‌خواهند.

## ۱۰.۳) Tier 2 — موتور درآمد (۸ ایجنت)
Lifecycle Growth · Content & Creative · CRO & Experiment · Revenue Intelligence · Sales/Offer · CRM & Retention · Support/Success · Trust/Compliance.

هر هشت ایجنت الگوی Agent Card §۳.۴ را کامل پر می‌کنند. دو نکتهٔ اجباری: Support/Success تنها ایجنتی است که ورودی `untrusted` دائمی دارد (تیکت کاربر) و بنابراین سقف L1 برای هر عملیات جهش‌دهنده دارد · Trust/Compliance مالک counter-KPI بیشتر ایجنت‌های رشد است و هرگز مالک KPI رشد نمی‌شود.

## ۱۰.۴) Counter-metric اجباری با مالکیت متقابل
سند در برابر شکست *فنی* محافظت می‌کند؛ این بند در برابر **موفقیت در متریک غلط** محافظت می‌کند. ایجنتی که انگیزهٔ گیم کردن یک KPI را دارد نمی‌تواند نگهبان همان KPI باشد.

```yaml
kpi:               [activation_rate, trial_to_paid]
counter_kpi:       [unsubscribe_rate, support_contact_per_user, refund_rate]
counter_kpi_owner: trust-compliance   # مالک متفاوت — اجبار در CI (I13)
```

CI رد می‌کند اگر `counter_kpi` خالی باشد یا `counter_kpi_owner == id`. رگرسیون counter-KPI بالاتر از آستانه = escalate + مسدود شدن ارتقای autonomy، حتی اگر KPI اصلی سبز باشد.

**Job ماهانهٔ «red-team the metrics»:** Adversarial Reviewer تلاش می‌کند نشان دهد هر KPI **بدون** ایجاد ارزش واقعی چگونه قابل بالا بردن است؛ خروجی → backlog guardrail + سناریوی جدید در `sim/scenarios/metric_gaming.yaml`.

## ۱۰.۵) قواعد مشترک همهٔ ایجنت‌ها
هیچ ایجنتی بدون Agent Card معتبر فعال نمی‌شود · هر ایجنت knowledge محدود به `owns` + MASTER-PLAN + BUILD-SPEC دارد · هر ایجنت heartbeat می‌فرستد (SLA در کارت) · هر ایجنت budget روزانه دارد، **قبل** از اجرا رزرو می‌کند و در ۸۰٪ escalate می‌کند · هیچ ایجنتی خودش را تأیید نمی‌کند (separation of duties) · هیچ ایجنتی مالک counter-KPI خودش نیست · هر ایجنت `standby_for` دارد؛ سه شکست پیاپی → جانشین با یک سطح autonomy کمتر · هر ایجنت باید بتواند در یک جمله بگوید «چرا این کار را کردم» و آن جمله در `receipt.why_one_sentence` ثبت شود.

* * *
# ۱۱) تداوم عملیات: مدل Solo-Operator و ریسک Bus-Factor
این بخش را جدی بگیر؛ همان چیزی است که اکثر سیستم‌های agentic در آن می‌میرند. واقعیت اندازه‌گیری‌شدهٔ این پروژه: **یک انسان، bus-factor = ۱.** طراحی صریحاً برای همین واقعیت است، نه برای یک سازمان فرضی.

## ۱۱.۱) Succession Protocol (خودکار)

```plain
TRIGGER: member removed | lease expired > TTL | 3 heartbeat متوالی گم‌شده
         | offboarding flag در Control Room | agent با ۳ شکست پیاپی

STEP 1  FREEZE      کارهای در جریان آن عضو/ایجنت → Blocked؛ lease با fencing token
                    جدید باطل؛ receipt وضعیت crashed/abandoned نوشته می‌شود
STEP 2  REVOKE      حذف دسترسی: Control Room، GitHub، Vault، A2A scope؛
                    rotation همهٔ secretهای لمس‌شده
STEP 3  RECONSTRUCT بازسازی وضعیت فقط از receipt chain + events
                    (نه از حافظهٔ آن شخص، نه از یک snapshot تأییدنشده)
STEP 4  REASSIGN    Orchestrator بر اساس capability match + standby_for
                    مالک جدید تعیین می‌کند؛ جانشین با autonomy یک سطح کمتر
STEP 5  BACKFILL    Docs & Knowledge شکاف دانش را از receipts به Runbook تبدیل می‌کند
STEP 6  VERIFY      smoke test مالکیت جدید + سناریوی sim مربوطه؛
                    تا سبز نشدن، workstream در حالت L1
STEP 7  REPORT      ADR + گزارش در Control Room + به‌روزرسانی CODEOWNERS
```

## ۱۱.۲) اصول ضدشکنندگی (بازطراحی‌شده برای یک اپراتور)
*   **Two-key = دو تبار مستقل، نه دو امضا.** «مستقل» تعریف عملیاتی دارد: مدل متفاوت **یا** prompt-lineage متفاوت، **به‌علاوهٔ** دسترسی به شواهد خام (نه خروجی کلید اول)، **به‌علاوهٔ** وظیفهٔ صریح رد کردن. یک ایجنت با همان مدل و همان context کلید دوم نیست — یک آینه است. مجری این نقش: `adversarial-reviewer`.
*   **CODEOWNERS واقعی:** انسان مالک **چهار** مسیر است و بس — `configs/pricing/**`، `**/ToS*`، `infra/terraform/**`، `security/iam/**`. بقیهٔ مسیرها مالک ایجنتی دارند با gate یک ایجنت مستقل. «خودت PR خودت را approve کن» تئاتر امنیتی است و حذف می‌شود.
*   **Escrow بازیابی (`RECOVERY.md` + بستهٔ رمزنگاری‌شده):** یک نفر **غیرفنی** باید بتواند با آن سیستم را متوقف کند یا واگذار کند. محتوا: مسیرهای kill switch به زبان ساده، فهرست دسترسی‌ها و نحوهٔ باطل کردن آن‌ها، مخاطبان، و «چه چیزی هرگز در این سیستم ذخیره نمی‌شود». بستهٔ رمزنگاری‌شده در `mirror` روزانه بازتولید می‌شود. bus-factor ۱ فقط با یک مسیر خروج انسانی مهار می‌شود، نه با ایجنت بیشتر.
*   **کانال خارج از باند (hard requirement):** Slack/Telegram. اگر Moxt و GitHub هر دو در دسترس نباشند، Owner هیچ راهی برای شنیدن alert ندارد. `messaging.out_of_band_alert` برای رویدادهای critical اجباری است و در `sim-nightly` تست می‌شود.
*   **Dead-man switch:** اگر Owner انسانی ۷۲ ساعت پاسخ ندهد، همهٔ capabilityهای L1 خودکار به «queue + hold» می‌روند، کارهای L2/L3 ادامه می‌یابند و سیستم در حالت safe-continue کار می‌کند. بعد از ۱۴ روز، تنزل به read-only. این مسیر در `sim/scenarios/owner_absent.yaml` تست می‌شود، نه فرض.
*   **هیچ دانش انحصاری انسانی مجاز نیست.** هر چیزی که فقط در سر یک نفر است، یک incident است. Docs & Knowledge هفتگی «knowledge concentration report» می‌سازد.
*   **Cold restore drill ماهانه با معیار امتیازدار:** از mirror + receipt chain یک محیط تازه بالا بیاور. معیار پذیرش (نه «۱۰۰٪ بازسازی» مبهم): (۱) STATE بازسازی‌شده با STATE اصلی برابر باشد به‌جز `generated_at` · (۲) زنجیرهٔ receipt از ریشه تا head معتبر · (۳) سه متریک کلیدی (CSR، NSM، receipt coverage) با اختلاف < ۱٪ بازتولید شوند · (۴) یک تسک ساختگی end-to-end در محیط بازیابی‌شده سبز شود. خروجی امتیازدار در `state/archive/drills/`.

* * *
# ۱۲) حلقهٔ اتوماسیون کامل (بدون انسان)
## ۱۲.۰) مرحله‌بندی توانایی حلقه (اعلام صریح، بدون حدس)
گام SENSE به داده‌ای نیاز دارد که در فازهای اول وجود ندارد. پس حلقه **مرحله‌ای** است و سطح خود را در هر event ثبت می‌کند:

```plain
Tick-A (از VS-1):  وضعیت مخزن، lease، receipt coverage، هزینهٔ توکن، سلامت CI، سلامت transport
Tick-B (+VS-7):    + SLO، CSR، probe fleet، error budget
Tick-C (+VS-8):    + funnel، activation، درآمد
Tick-D (+VS-9):    + خوانش آزمایش، autonomy ratchet، shadow agreement
```

اگر ورودی لازم غایب باشد → `degraded_sense` در STATE و event ثبت می‌شود و تصمیم‌های وابسته به آن ورودی **مسدود** می‌شوند. حدس زدن ممنوع است؛ کار کردن با داده تقلبی ممنوع‌تر.

## ۱۲.۱) Tick (تطبیقی — رویدادمحور با کف ۳۰ دقیقه و backoff تا ۴ ساعت)

```plain
0 GATE      SENSE ارزان (هش متریک‌ها) + خواندن kill switch + budget forecast
            → اگر تغییر معنادار نبود: backoff، خروج ارزان
            → اگر kill switch ناخوانا: halt (fail-closed)
1 SENSE     خواندن ورودی‌های سطح tick جاری (§۱۲.۰)
2 DIAGNOSE  مقایسه با baseline و هدف؛ تشخیص leak/regression/فرصت
3 DECIDE    حداکثر ۳ اقدام با بیشترین expected value ÷ risk (مدل رده‌بالا)
4 ROUTE     ساخت A2A envelope با idempotency class، deadline، budget reservation
5 EXECUTE   ایجنت‌های تخصصی موازی (حداکثر ۵ همزمان، مشروط به بودجهٔ رزروشده)
6 VERIFY    QA/Security gate + probe واقعی + بازبینی خصمانه روی مسیر بحرانی
7 COMMIT    receipt (با prev_receipt_hash) + event + commit atomic + Control Room mirror
8 LEARN     backlog فرضیه، autonomy ratchet + shadow agreement، تسویهٔ بودجه
9 GUARD     هر guardrail قرمز یا رگرسیون counter-KPI → rollback + قرنطینه + escalate
```

## ۱۲.۲) تنها موارد ورود انسان
تغییر قیمت · خروج پول · تغییر زیرساخت غیرقابل‌بازگشت · تغییر ToS/Privacy/حوزهٔ قضایی · حادثهٔ امنیتی Sev1 · **غیرفعال‌سازی** kill switch. بقیهٔ ۹۵٪ باید بدون انسان بچرخد. اگر `intervention_rate` از ۵٪ کارها بالاتر رفت، آن یک باگ است نه یک ویژگی: علتش را به‌عنوان تسک ثبت کن و سناریوی sim بساز.

* * *
# ۱۳) Growth، Revenue و Experimentation
## ۱۳.۱) Event Taxonomy (حداقل مجموعه، first-party)
`page_view · signup_started · trial_created · client_guide_viewed · config_downloaded · first_connection_attempt · first_connection_success · connection_health_sample · checkout_started · payment_succeeded · provision_completed · renewal_due · renewal_succeeded · usage_drop · support_contact · refund_requested · referral_shared · reactivated`

هر event: `name, actor(anon key), ts, source, campaign, consent_state, schema_version, correlation_id, trust`. مالک: Analytics Engineer. **ذخیرهٔ محتوای ترافیک و مقصد کاربر ممنوع** — این ممنوعیت در `security/compliance/` هم ثبت و در تست‌های امنیتی اجبار می‌شود.

## ۱۳.۲) North Star
**تعداد کاربران پرداختی با حداقل یک اتصال موفق و پایدار در پنجرهٔ ۷ روزه.** همهٔ داشبوردها باید بتوانند به این عدد تجزیه شوند و هر عدد به event خام قابل ردیابی باشد. تغییر تعریف NSM فقط با ADR.

## ۱۳.۳) Unit economics (فرمول‌های اجرایی در `analytics/models/`)

```plain
GrossProfitPerUser = ARPU − infra/user − payment_fee − support_cost − agent_token_cost/user
LTV = ARPU × gross_margin × expected_lifetime_months
Targets: LTV:CAC > 3 · CAC payback < 3mo · gross_margin > 70%
Stop-loss: هر کمپین با CAC > 1.5× هدف در ۴۸ ساعت خودکار متوقف می‌شود
```

`agent_token_cost/user` عمداً در فرمول است: هزینهٔ خودمختاری یک هزینهٔ واقعی واحد اقتصادی است، نه سرباری پنهان.

## ۱۳.۴) Experiment Engine
قرارداد آزمایش طبق MASTER-PLAN §۹.۲، با این الزامات: محاسبهٔ خودکار sample size قبل از شروع (power ۰.۸، alpha ۰.۰۵) · sequential testing با always-valid p-value برای توقف زودهنگام ایمن · SRM check در هر readout · ثبت اجباری «negative result» · guardrail با stop condition عددی. workflow `experiment` هر ۳۰ دقیقه guardrail را چک و در صورت نقض خودکار stop و rollback می‌کند.

**همین موتور، gate ارتقای canary است** (§۵.۷). یک پیاده‌سازی آماری، دو کاربرد — نه دو کد نیمه‌درست.

* * *
# ۱۴) Observability، SLO و Error Budget

| SLI | SLO | پنجره | واکنش نقض |
| ---| ---| ---| --- |
| Connection Success Rate | ≥ ۹۸٪ | ۷ روز غلتان | فریز release، Config Agent به L1 |
| P95 latency | ≤ هدف مسیر | ۲۴ ساعت | reroute + probe |
| Provisioning time | ≤ ۶۰ ثانیه | ۲۴ ساعت | صف پرداخت بررسی شود |
| Checkout success | ≥ ۹۵٪ | ۷ روز | مسیر پرداخت جایگزین |
| A2A task success | ≥ ۹۷٪ | ۷ روز | تنزل autonomy |
| **Receipt coverage** | **۱۰۰٪ تسک‌ها receipt دارند (هر `status`)** | همیشه | build شکست |
| **Crash rate** | **< ۲٪ تسک‌ها با `status: crashed`** | ۷ روز | تحقیق ریشه‌ای + سناریوی sim + تنزل autonomy |
| Transport availability | T1 ≥ ۹۹٪، مسیر پیش‌فرض ≥ ۹۵٪ | ۷ روز | fallback + رویداد degraded |
| Kill switch readability | ۱۰۰٪ | همیشه | fail-closed engaged + incident |
| Chain integrity | ۱۰۰٪ | همیشه | incident امنیتی |

تفکیک receipt coverage از crash rate عمدی است: invariant «هیچ کار بدون receipt» فقط وقتی اجراشدنی است که crash خودش یک receipt معتبر (`tombstone`) تولید کند. یک invariant قابل‌اجرا جای یک invariant اخلاقی را می‌گیرد — گateی که در هفتهٔ دوم خاموش شود، بدتر از نبودن است.

Error budget policy: مصرف > ۵۰٪ → فقط کارهای reliability · > ۱۰۰٪ → همهٔ featureها و کمپین‌ها فریز تا بازیابی. Stack: Prometheus + Grafana + Loki + OpenTelemetry، probe fleet طبق §۵.۷، chaos drill ماهانه در `sim/` و فصلی در محیط واقعی.

* * *
# ۱۵) امنیت و حریم خصوصی
## ۱۵.۱) خط پایه
GitHub App یا fine-grained token (Classic PAT ممنوع) · OIDC برای Actions · SOPS+age یا Vault با token کوتاه‌عمر · gitleaks در CI و در PreCommit روی staged diff · CODEOWNERS چهارمسیرهٔ انسانی + protected main + signed commits · transport با احراز هویت و scope و replay protection · least privilege برای هر ایجنت · حداقل داده، no-content-logs، retention اجباری (event خام ۹۰ روز، aggregate نامحدود) · consent state در هر event · هر حادثه: Detect → Contain → Eradicate → Recover → Postmortem با ADR.

## ۱۵.۲) دفاع Prompt Injection — معماری، نه اعلامیه
«محتوای خارجی داده است نه دستور» یک هدف است؛ این بند مکانیزم اجبار آن است.

**Taint tracking در envelope (§۳.۵):**

```json
"input_provenance": [
  {"field":"$.ticket.body","source":"support:zendesk#8123",
   "trust":"untrusted","sanitizer":"envelope-v1","content_hash":"sha256:..."}
]
```

*   سه سطح اعتماد: `owner` > `internal` > `untrusted`. سطح **ارث می‌برد**: هر مشتق از یک فیلد untrusted، untrusted است.
*   **قانون سخت (I16):** فراخوانی هر ابزار جهش‌دهنده که پارامترش از فیلد `untrusted` مشتق شده، به Policy Engine می‌رود و **حداکثر L1** می‌گیرد — بدون استثنا. اجبار در `hooks/pre_tool.py` و در `scripts/lib/taint.py`.
*   `capability_grant` توسط منبع اعتماد (dispatcher در T1 / Gateway در T3) **امضا** می‌شود و هرگز از payload مشتق نمی‌شود. ایجنت نمی‌تواند capability خودش را از متن ورودی استخراج کند.
*   محتوای خارجی همیشه با مرز صریح در envelope: `<<UNTRUSTED_DATA source=... >> … <<END>>`. حذف مرز = خطای schema.
*   خروجی ایجنت قبل از اجرا schema-validate می‌شود؛ خروجی خارج از schema اجرا نمی‌شود.
*   مجموعهٔ تست injection در `sim/scenarios/prompt_injection.yaml`؛ معیار پذیرش §۱۶: صفر یافتهٔ high.

## ۱۵.۳) انطباق، حوزهٔ قضایی و درخواست قانونی (`security/compliance/`)
برای یک کسب‌وکار در این دامنه، نداشتن این بخش یک نقطهٔ کور است، نه یک سادگی.

*   `compliance-register.md` — تعهدها، مبنا، مالک، تاریخ بازبینی.
*   `legal-request-playbook.md` — چه کسی پاسخ می‌دهد، **چه داده‌ای وجود دارد و چه داده‌ای وجود ندارد**، چه چیزی هرگز ثبت نمی‌شود (محتوای ترافیک، مقصد کاربر)، مسیر تشدید، و قالب پاسخ.
*   `data-residency.md` — جدول محل داده به‌ازای هر Adapter و هر provider.
*   `payments-compliance-review.md` — بازبینی انطباق مسیر پرداخت.

**همهٔ این‌ها L0 هستند: ایجنت فقط پیشنهاد می‌دهد، تصمیم انسانی است.** Security & Compliance مالک نگهداری فایل‌ها است، نه مالک تصمیم.

* * *
# ۱۶) Simulation Harness — اثبات ۷۲ ساعت در ۶۰ ثانیه
ادعای «۷۲ ساعت بدون انسان» بدون محیط شبیه‌سازی قابل اثبات نیست. جایگزین واقعی آن دو حالت است: تست روی کاربران واقعی Marzneshin، یا امضای DoD با یک ادعا. هر دو رد می‌شوند. `sim/` بالاترین بازده در کل این معماری است و یک اسلایس درجه‌یک است (VS-2).

```plain
sim/
├─ clock.py       ساعت مجازی — ۷۲ ساعت شبیه‌سازی در < ۶۰ ثانیهٔ دیواری
├─ world.py       دنیای شبیه‌سازی: nodes، کاربران، funnel، درآمد، حادثه، هزینه
├─ fakes/         fake همهٔ Adapterها با همان contract test نسخهٔ واقعی
├─ scenarios/     YAML: node_outage · payment_provider_down · agent_crash_mid_task
│                 lease_expiry · cost_spike · prompt_injection · metric_gaming
│                 control_room_down · gateway_down · owner_absent · clock_skew
│                 config_canary_regression · probe_fleet_down · killswitch_unreadable
├─ chaos.py       تزریق خطا با seed → بازتولید دقیق
└─ report.py      خروجی امتیازدار: MTTR، کار تکراری، receipt coverage، نقض guardrail،
                  هزینهٔ توکن، تعداد مداخلهٔ لازم
```

قواعد اجباری:
*   **هیچ کد نویی وارد مسیر production نمی‌شود مگر ابتدا در `sim/` سبز شود** (I11).
*   هر باگ production یک سناریوی رگرسیون در `sim/scenarios/` می‌سازد — بدون استثنا.
*   `seed` در receipt ثبت می‌شود ⇒ هر شکست دقیقاً بازتولیدشدنی است.
*   fake و adapter واقعی **همان** contract test را پاس می‌کنند؛ واگرایی آن‌ها = شبیه‌سازی بی‌ارزش.
*   `world: sim` در همهٔ eventها؛ event شبیه‌سازی هرگز به پارتیشن production نمی‌رود.
*   CI شبانه (`sim-nightly`): کل مجموعهٔ سناریو با ۱۰ seed تصادفی + `killswitch.py --verify`.

## ۱۶.۱) استراتژی تست و پذیرش

| لایه | تست | معیار پذیرش |
| ---| ---| --- |
| Unit | schema، policy rule، adapter، upcaster | coverage ≥ ۸۰٪ روی `scripts/lib`، policy و adapters |
| Contract | هر adapter در برابر fake + sandbox | ۱۰۰٪ opها، همان suite برای fake و واقعی |
| Migration | round-trip upcaster روی نمونه‌های آرشیو | ۱۰۰٪ eventهای تاریخی خواندنی |
| Integration | A2A end-to-end روی T1 **و** T2 با ۳ ایجنت | task success ≥ ۹۷٪ در هر دو transport |
| Chain | `verify.py --chain` از ریشه | ۱۰۰٪ صحت زنجیرهٔ receipt |
| Chaos (sim) | کشتن ایجنت وسط کار، انقضای lease، قطع provider، skew ساعت | بازیابی خودکار < ۱۵ دقیقهٔ مجازی، بدون کار تکراری، tombstone صحیح |
| Autonomy (sim) | ۷۲ ساعت مجازی با ۱۰ seed | صفر مداخلهٔ لازم، receipt coverage ۱۰۰٪، صفر guardrail breach |
| Continuity | حذف یک عضو، cold restore | معیار چهارگانهٔ §۱۱.۲ |
| Safety | `killswitch.py --verify` روی ۵ مسیر + fail-closed | توقف واقعی در هر ۵ مسیر و در حالت ناخوانا |
| Security | gitleaks، SAST، injection suite | صفر یافتهٔ high |
| Business | canary روی funnel واقعی با `n ≥ n_min` | بدون افت guardrail، نتیجهٔ آماری قطعی |

* * *
# ۱۷) ترتیب ساخت — ۱۲ Vertical Slice
**هیچ‌وقت دو اسلایس هم‌زمان.** هر اسلایس با DoD کامل بسته می‌شود. ترتیب طوری چیده شده که هیچ تماسی با کاربر واقعی قبل از اثبات continuity، kill switch و rollback رخ ندهد.

| # | اسلایس | تحویل‌دادنی | Definition of Done |
| ---| ---| ---| --- |
| VS-1 | **Spine** | repo، CLAUDE.md، STATE/HANDOFF/events پارتیشن‌شده، receipt chain، ۷ hook (رده A + pre_push)، `scripts/lib/`، workflowهای validate+compact+mirror | یک تسک ساختگی از CLAIM تا HANDOFF با receipt `complete`، زنجیرهٔ معتبر، و `verify.py --chain` سبز |
| VS-2 | **Simulation Harness** | `sim/` کامل: clock، world، fakes همهٔ Adapterها، ۶ سناریوی اول، chaos با seed، report امتیازدار | یک سناریوی ۷۲ ساعت مجازی در < ۶۰ ثانیه اجرا شود، با seed بازتولیدشدنی، و گزارش امتیازدار تولید کند |
| VS-3 | **A2A over T1/T2** | envelope §۳.۵، dispatcher T1 (`a2a-dispatch.yml`)، T2 روی Moxt Workflow، Registry، Policy Engine حداقلی، سه کلاس idempotency | یک task واقعی میان دو ایجنت روی **هر دو** transport با audit، idempotency اثبات‌شده (تکرار = بدون اجرای دوباره) و fallback خودکار T2→T1 |
| VS-4 | **Continuity + Kill Switch** | succession workflow، reaper + tombstone، dead-man switch، kill switch ۵ مسیره fail-closed، `RECOVERY.md` + بستهٔ escrow، کانال خارج از باند | هر ۵ مسیر kill switch در sim عملاً متوقف کند · حالت «ناخوانا» halt کند · حذف شبیه‌سازی‌شدهٔ یک عضو بدون توقف پروژه · cold restore با معیار چهارگانهٔ §۱۱.۲ سبز |
| VS-5 | **Tier 0 Agents (۷ ایجنت)** | ۷ Agent Card کامل، budget reservation، heartbeat، QA gate، Handoff Guardian فعال، Adversarial Reviewer با تبار مستقل | یک تغییر بحرانی که Adversarial Reviewer آن را **رد** کند و ثبت شود · continuity score تولید شود · هیچ ایجنتی خودش را تأیید نکند (اثبات در audit) |
| VS-6 | **Control Room** | Moxt Workflow با statusها و فیلدهای §۹، sync یک‌طرفه، دو استثنای برگشتی، Views | تغییر در GitHub در < ۶۰ ثانیه در Control Room دیده شود · تغییر فیلد Approval به GitHub برگردد · هیچ فیلد دیگری معکوس sync نشود |
| VS-7 | **Config Pipeline** | canary ۱٪→۱۰٪→۵۰٪→۱۰۰٪ به‌عنوان experiment، probe fleet سه‌ASN، `n_min`، always-valid p-value، auto-rollback | یک rollback واقعی تست‌شده و ثبت‌شده · یک مورد `inconclusive` که ارتقا را **متوقف** کرده باشد · fail-closed در نبود probe سالم |
| VS-8 | **Growth Spine** | event taxonomy، JSON Schemaها + upcaster اول، checkout، funnel dashboard، journey اول، Analytics Engineer فعال | NSM از داده واقعی محاسبه شود و هر عدد به event خام قابل ردیابی باشد · یک مهاجرت schema با round-trip سبز |
| VS-9 | **Experiment Loop** | experiment engine (همان موتور VS-7)، guardrail، SRM، readout، ۳ تست کم‌ریسک | یک تصمیم ship/kill مستند با evidence · یک negative result ثبت‌شده · یک auto-stop واقعی روی نقض guardrail |
| VS-10 | **Revenue Command Center** | داشبوردهای MASTER-PLAN §۸ روی Mini App + Grafana، unit economics، counter-KPI panel | هر عدد به event خام قابل ردیابی · `agent_token_cost/user` در فرمول سود زنده باشد |
| VS-11 | **Autonomy Ratchet + Shadow Mode** | ارتقا/تنزل خودکار، ثبت تصمیم سایه، `/autonomy-review` با قرارداد خروجی، red-team the metrics | یک ارتقای autonomy با سه شرط §۶.۲ (۳۰ اجرای پاک + ۹۵٪ توافق سایه در ۲۰ نمونه + sim سبز) · ۷۲ ساعت اجرای بدون مداخله، ابتدا در sim با ۱۰ seed سپس در production |
| VS-12 | **(اختیاری) HTTP Gateway** | `gateway/` طبق §۵.۳ به‌عنوان کش latency | فقط اگر latency T1/T2 اثباتاً محدودکننده شده باشد (با داده) · همهٔ تست‌های ایمنی با T3 **خاموش** هم سبز بمانند (I14) |

منطق ترتیب: `sim` قبل از هر چیزی که باید اثبات شود · continuity و kill switch قبل از هر تماس با production · Control Room بعد از ایجنت‌ها (چون فیلدهای UI را نیاز واقعی ایجنت تعیین می‌کند، نه حدس) · Gateway آخر و اختیاری.

* * *
# ۱۸) Trade-off Register (صریح، نه پنهان)
«بدون trade-off» وجود ندارد؛ هدف واقعی این است: **trade-off آگاهانه، محدود، ثبت‌شده و قابل‌برگشت.** این جدول در `decisions/TRADEOFF-REGISTER.md` زنده نگه داشته می‌شود (I8).

| انتخاب | منفعت | هزینه | مهار |
| ---| ---| ---| --- |
| GitHub SSoT | اکوسیستم، Actions، audit رایگان | وابستگی به پلتفرم | mirror روزانه + cold clone + adapter |
| Transport سه‌لایه به‌جای Gateway اجباری | حذف SPOF، تحویل بدون زیرساخت | سه مسیر برای نگهداری | envelope مشترک · contract test یکسان · T3 اختیاری |
| Event sourcing | replay، تعارض کمتر | حجم و نیاز به compact | compact ساعتی + archive + upcaster |
| اتوماسیون کامل | سرعت و هزینهٔ کمتر | blast radius خطا | autonomy levels + kill switch + rollback |
| Sequential testing | تصمیم سریع‌تر | پیچیدگی آماری | always-valid p-value + SRM check + یک موتور مشترک |
| Personalization | conversion بالاتر | ریسک privacy | first-party + consent + حداقل داده |
| چند مسیر پروتکل | تاب‌آوری | هزینه و نگهداری بیشتر | اولویت بر اساس SLO، حداکثر ۳ مسیر |
| Multi-agent | تخصص و موازی‌سازی | هزینهٔ توکن و هماهنگی | budget per agent + reservation + Context Efficiency KPI |
| **D1 — T1 به‌عنوان baseline** | صفر زیرساخت، audit ذاتی | latency ۳۰–۹۰ ثانیه | T2 برای مسیرهای حساس به latency؛ T3 در VS-12 |
| **D3 — Control Room بومی Moxt** | حذف SaaS پرداختی از مسیر Governance | بدون داشبورد تحلیلی آماده | Mini App + Grafana در VS-10 |
| **D4 — حذف total order** | حذف ساختاری merge conflict و retry storm | استدلال دربارهٔ ترتیب سخت‌تر | ULID + زنجیرهٔ causation + `actor_seq` + تست replay |
| **D5 — fail-closed سراسری** | «نمی‌دانم» هرگز به «مجاز» ترجمه نمی‌شود | توقف‌های کاذب در قطعی شبکه | پنج مسیر مستقل + پنجرهٔ ۱۵ دقیقه + verify شبانه |
| **D6 — sim اجباری قبل از prod** | اثبات صادقانه بدون ریسک کاربر | هزینهٔ ساخت پیش‌پرداخت (~یک اسلایس) | همان هزینه در VS-4..VS-11 بازیافت می‌شود |
| **D7 — بازبین خصمانه** | کلید دوم واقعی در سازمان تک‌نفره | هزینهٔ توکن بیشتر به‌ازای هر تغییر بحرانی | فقط روی مسیرهای بحرانی، نه همهٔ کارها |

* * *
# ۱۹) Definition of Done نهایی
یک initiative فقط وقتی Done است که **همهٔ** این‌ها درست باشند:

مسئله و hypothesis روشن · owner/scope/budget/success metric مشخص · counter-KPI با مالک متفاوت تعیین‌شده · artifact در مسیر درست (`owns`) commit شده · سناریوی مربوطه در `sim/` سبز · تست فنی، امنیتی و تجاری اجرا شده با خروجی واقعی · receipt با `status` معتبر + `prev_receipt_hash` + evidence + event + HANDOFF ثبت · زنجیرهٔ receipt معتبر · CI سبز · rollback **عملاً تست شده** با `tested_at` · dashboard و alert ساخته شده · ADR یا experiment report ثبت · Control Room mirror شده · budget تسویه شده · lease آزاد.

* * *
# ۲۰) خروجی مورد انتظار از Claude Opus 5
در پاسخ اول، دقیقاً این‌ها را بده و بعد بلافاصله VS-1 را بساز:

1.  **Repo scaffold کامل** طبق §۲.۲ با محتوای واقعی فایل‌ها (نه placeholder، نه فایل خالی).
2.  **`CLAUDE.md` نهایی** + `CONTEXT-PACK.md` اولیه + `STATE.json` صفر طبق §۳.۱ + `RECOVERY.md`.
3.  **هفت hook اجرایی** (رده A + pre_push) با تست، بدون I/O شبکه.
4.  **چهار workflow** (`validate`, `compact`, `mirror`, `heartbeat`) که سبز شوند.
5.  **یک receipt نمونهٔ واقعی** از یک تسک end-to-end با زنجیرهٔ معتبر و `sim_evidence`.
6.  **`scripts/lib/` پایه** (state، events، receipts، leases، taint، budget، transport، redact) با تست.
7.  **ADR برای هر تصمیمی که خودت گرفتی** و در این سند نیست.
8.  **گزارش GAP جدید:** هر جای این سند که با واقعیت ابزارها نمی‌خواند، صریح بگو و جایگزین پیشنهاد بده. سکوت کردن روی شکاف = نقض قرارداد.

هر پاسخ با یک بلوک وضعیت تمام می‌شود:

```plain
SLICE: VS-x | STATUS: green|amber|red
DONE: ... | NEXT: ... | BLOCKERS: ... | RECEIPTS: ... | TOKENS: ...
```

* * *
## پنج قانون آهنین
1.  هیچ کانفیگی بدون QA به کاربر نمی‌رسد.
2.  هیچ کمپینی بدون hypothesis و stop condition اجرا نمی‌شود.
3.  هیچ جلسه‌ای بدون HANDOFF تمام نمی‌شود.
4.  هیچ secretی وارد مخزن نمی‌شود.
5.  هیچ تصمیمی بدون owner، evidence و rollback پذیرفته نمی‌شود.

**و یک قانون ششم که v2.0 اضافه می‌کند:** «نمی‌دانم» هم‌ارز «متوقف شو» است. هر کنترل ایمنی که وضعیتش خوانده نشود، فعال فرض می‌شود — نه غیرفعال.
