# GAP-REPORT-004 — SYNC + بستن VS-2 (Simulation Harness) با شواهد سناریوی واقعی

> **مرجع:** BUILD-SPEC v2.0 §۱۶/§۱۷ · ADR-001..004 · GAP-REPORT-003
> **نویسنده:** momo (جلسهٔ S-2026-07-30-VS2-close، سومین workspace — ادامهٔ پروژه با zip جدید) · **تاریخ:** 2026-07-30
> **وضعیت:** **VS-2 بسته شد.** هر سه شکاف ورودی با تصمیم مستند (ADR-004) بسته شد و DoD اسلایس با ۱۸ اجرای واقعی سناریو ارضا شد. اسلایس بعدی: **VS-3 (A2A over T1/T2)**.

---

## ۰) خلاصهٔ اجرایی

1. **zip ورودی جدیدتر از GAP-REPORT-003 بود** — درست مثل جلسهٔ قبل که zip جدیدتر از GAP-REPORT-002 بود. VS-2 **نیمه‌ساخته** یافت شد: هارنس کامل `sim/` (world, actors, chaos, report, ۹ fake، ۶ سناریو، runner) + ۱۷ تست. طبق دستور Owner، **هیچ بخش ساخته‌شده‌ای بازسازی نشد.**
2. **سه شکاف واقعی مانده بود و هر سه در این جلسه بسته شدند:** (الف) contract vault در C3 (payload منطقاً ارضاناپذیر) · (ب) ۵ تخطی `lint-clock` در ۳ فایل · (ج) تداخل نام `sim` در sys.path تست‌ها. تصمیم‌ها: ADR-004 (D23–D26).
3. **DoD خودِ VS-2 با شواهد واقعی بسته شد:** ۶ سناریو × ۳ seed = **۱۸/۱۸ PASS** (۷۲ ساعت مجازی در ۰٫۲–۰٫۵ ثانیهٔ دیواری، score ۱٫۰) · گزارش امتیازدار در `artifacts/sim/VS2-closeout.json` · ۱۳۲/۱۳۲ تست · `verify --all` سبز · ۱۰/۱۰ drill کیل‌سوییچ · receipt زنجیره‌ای T-0006 با `sim_evidence` از سناریوهای واقعی (پل D20 بازنشسته شد).

**ادعایی که این گزارش نمی‌کند:** adapterهای *واقعی* (VS-3)، Agent Cardها (VS-5)، Control Room (VS-6) هنوز وجود ندارند. fakes کامل‌اند و قرارداد §۴ را پاس می‌کنند — adapter واقعی بدون credential (O3) ساخته نمی‌شود.

---

## ۱) SYNC — وضعیت یافته‌شده در ورود

| مورد | GAP-REPORT-003 گفت | واقعیت در zip این جلسه |
| --- | --- | --- |
| `sim/` کامل (N8) | «شروع‌نشده — گام بعدی» | ✅ موجود: runner ۲۲۶ خط، world ۲۰۸، actors ۴۴۰، chaos ۱۱۱، report ۷۳، fakes ۳۰۴+۸۷، ۶ سناریو، ۱۷ تست |
| contract test ۹ fake (§۴/§۱۶.۱) | — | ⚠️ موجود ولی vault قرمز (C3) |
| `lint-clock` | سبز در VS-1 | ❌ ۵ تخطی جدید از فایل‌های VS-2/VS-3 |
| tests ۱۱۵/۱۱۵ | سبز | ❌ ۱ خطای import + ۲ fail روی ۱۳۲ تست |
| `adapters/base.py` + `contract.py` (VS-3) | «شروع‌نشده» (N9) | ⚠️ پروتکل و قرارداد شروع شده؛ adapter واقعی نه |

اقدام‌های SYNC طبق پروتکل §۰: lease زامби جلسهٔ قبل (token=2، منقضی) با claim جدید (token=3) جایگزین شد · kill switch روی کلون تازه UNKNOWN بود (fail-closed طبق طراحی) و با `killswitch.py reconcile --skip-auto --by momo` به RUNNING برگشت.

## ۲) PLAN (حداکثر ۷ گام، هر کدام یک artifact)

1. ترتیب sys.path در `tests/test_sim.py` → import پایدار ✅
2. `sim/world.py` — بازنویسی docstring + معافیت مستند RNG ✅
3. `adapters/base.py` — مهلت و backoff از lib/clock ✅
4. `adapters/contract.py` — `_deadline` از lib/clock + fixture vault ✅
5. `sim/fakes/__init__.py` — pre-seed `contract/probe` ✅
6. دروازه‌ها: unittest + verify --all + killswitch verify + sim suite ۱۸ اجرا → `artifacts/sim/VS2-closeout.json` ✅
7. EMIT + HANDOFF: رویدادها، receipt T-0006، ADR-004، این گزارش، HANDOFF.md، CONTEXT-PACK ✅

## ۳) شواهد اجرا (خروجی واقعی، نه ادعا)

| دروازه | دستور | نتیجه |
| --- | --- | --- |
| تست واحد + CLI + هارنس | `python3 -m unittest discover -s tests` | **۱۳۲/۱۳۲ OK** (۱۱۵ قبلی + ۱۷ sim) |
| دروازه‌های CI | `scripts/verify.py --all` | **GREEN (۶/۶)**: chain، events، schemas (13)، agent-cards، lint-imports، lint-clock |
| تمرین کیل‌سوییچ | `scripts/killswitch.py verify` | **۱۰/۱۰** (۵ مسیر + fail-closed) |
| **DoD §۱۷ VS-2** | `scripts/sim.py run --all --seeds 11,27,43` | **۱۸/۱۸ PASS** — ۷۲h مجازی در ۰٫۲۱۵–۰٫۵۳۷s، score ۱٫۰، checks ۷/۷ در همه |
| بازتولید با seed | `test_seed_makes_run_exactly_reproducible` | دو اجرای seed=42 بایت‌به‌بایت یکسان (به‌جز duration/artifacts) |
| tombstone و زنجیره | `test_crash_scenario_produces_tombstone...` | crash_rate>۰، chain_ok، coverage=۱٫۰، duplicate_work=۰ |
| تزریق prompt | `test_prompt_injection_never_grants_above_l1` | guardrail_breaches=۰ (I16) |
| کانال OOB | `test_out_of_band_alert_is_recorded` | هشدار §۱۱.۲ واقعاً ثبت می‌شود |

گزارش خام: `artifacts/sim/VS2-closeout.json` (۱۸ گزارش امتیازدار با metrics کامل: MTTR، کار تکراری، receipt coverage، نقض guardrail، هزینهٔ توکن، مداخله).

## ۴) DoD خودِ VS-2 (BUILD-SPEC §۱۷) — جدول اثبات

| معیار DoD | شاهد | وضعیت |
| --- | --- | --- |
| سناریوی ۷۲ ساعتهٔ مجازی در < ۶۰ ثانیهٔ دیواری | ۱۸ اجرا، سقف ۰٫۵۳۷s — ۱۱۲× سریع‌تر از آستانه | ✅ |
| بازتولیدشدنی با seed | تست replay + seed در event/receipt | ✅ |
| گزارش امتیازدار | `sim/report.py` + `artifacts/sim/VS2-closeout.json` (score ۱٫۰) | ✅ |
| fakes همهٔ adapterها با همان contract test | ۹/۹ fake × C1–C8 سبز (D23) | ✅ |
| ۶ سناریوی اول §۱۶ | node_outage · payment_provider_down · agent_crash_mid_task · lease_expiry · cost_spike · prompt_injection | ✅ |

## ۵) فهرست «شروع‌نشده» پس از این جلسه (به‌روز از GAP-REPORT-003)

| # | مورد | اسلایس | یادداشت |
| --- | --- | --- | --- |
| N9 | `adapters/` واقعی (۹ adapter روی sandbox) | **VS-3** | پروتکل + قرارداد + ۹ fake ✅ آماده؛ fixture vault (D23) باید در sandbox واقعی seed شود · مسدود به O3 |
| N9b | A2A: envelope §۳.۵ · dispatcher T1 (`a2a-dispatch.yml`) · T2 روی Moxt Workflow · Registry · Policy Engine | **VS-3** | schemaهای `a2a-envelope` و `agent-card` از VS-1 موجودند |
| N10 | `agents/cards/` — ۷ Agent Card Tier 0 | VS-5 | schema + قواعد CI آماده |
| N11 | `skills/` — ۱۱ SKILL.md با هدر §۷.۳ | VS-5+ | **الگوی gstack این جلسه بازبینی مجدد شد** (github.com/garrytan/gstack — ۲۳ skill: qa/review/freeze/guard/ship/canary/retro/careful) → نگاشت مستقیم به QA gate، Adversarial Reviewer و freeze protocol پروژه |
| N12–N15 | `mcp/` · `growth/` · `analytics/` · ۷ workflow CI باقی · `gateway/` (ممنوع) | VS-3..VS-12 | بدون تغییر |
| N18 | Moxt Workflow «Control Room» + AI Teammates | VS-6/VS-3 | در همین workspace ساخته می‌شود |

## ۶) gstack و Moxt — مصرف در این جلسه و نقشهٔ بعد

- **gstack** (github.com/garrytan/gstack): مرجع ساختار SKILL.md برای N11 بازبینی شد. نگاشت قابل استفاده در VS-5: `/qa` → QA gate · `/review` + lineage مستقل → Adversarial Reviewer · `/freeze` + `/guard` → kill-switch/freeze protocol · `/canary` → Config Pipeline (VS-7) · `/retro` → autonomy-review (VS-11). الگوی «frontmatter کوتاه + trigger صریح» آن با هدر §۷.۳ سازگار است.
- **Moxt**: مصرف واقعی در اسلایس‌های بعد: Control Room (VS-6، Moxt Workflow با فیلدهای §۹) و T2 transport (VS-3، dispatch روی Moxt Workflow) + AI Teammates برای ۷ ایجنت Tier 0. در این جلسه، قراردادهای آن (schemaهای a2a/agent-card) از VS-1 سبز نگه داشته شدند.

## ۷) اقدام‌های باز Owner (بدون تغییر، تکرار از GAP-REPORT-003)

O1 قیمت مدل‌ها · O2 MASTER-PLAN/قرارداد آزمایش (VS-9/10 را مسدود می‌کند؛ VS-3 آزاد است) · O3 GitHub token (VS-3 T1 dispatcher و push واقعی) · O4 کانال OOB واقعی (VS-4) · O5 venv/CI با `jsonschema`+`pyyaml` — **در این جلسه محلياً تأمین شد** (`/tmp/mops-venv`)؛ validate.yml در CI نصب می‌کند.

## ۸) وضعیت

```plain
SLICE: VS-2 | STATUS: green — DoD بسته شد با شواهد (۱۸/۱۸ سناریو × ۳ seed، ۱۳۲/۱۳۲ تست، verify سبز، ۱۰/۱۰ drill)
DONE:  بستن ۳ شکاف (vault contract، lint-clock ×۵، تداخل import) بدون بازسازی هیچ بخش ساخته‌شده
       · ADR-004 (D23–D26) · بازنشستگی پل D20 · artifacts/sim/VS2-closeout.json · receipt T-0006
NEXT:  VS-3 (A2A over T1/T2) طبق §۱۷: envelope §۳.۵ + dispatcher T1 + T2 روی Moxt Workflow
       + Registry + Policy Engine حداقلی — پیش‌نیازها: schemaها ✅، fakes ✅، fixture vault (D23)
BLOCKERS: O3 (GitHub token) فقط برای T1 واقعی/push · بدون blocker برای ساخت envelope/Registry/Policy
RECEIPTS: receipts/2026/07/T-000{1..6}.json — زنجیرهٔ agentic-core، head index 5
TOKENS: این جلسه: بستن VS-2 (ادامه‌دهنده، نه بازساز — zip جدیدتر از GAP-REPORT-003 بود)
```
