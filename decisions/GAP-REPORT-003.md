# GAP-REPORT-003 — SYNC + GAP SCAN + ساخت VS-1 (بستن اسلایس Spine)

> **مرجع:** BUILD-SPEC v2.0 · ADR-001/002/003 · GAP-REPORT-001/002
> **نویسنده:** Owner فنی (جلسهٔ ادامه پس از مهاجرت به اکانت/workspace جدید) · **تاریخ:** 2026-07-30
> **مبنای قرارداد:** BUILD-SPEC §۰ پروتکل جلسه · §۲۰ خروجی مورد انتظار
> **وضعیت:** **VS-1 بسته شد.** DoD اسلایس با شواهد اجراشده ارضا می‌شود. اسلایس بعدی: VS-2 (Simulation Harness).

---

## ۰) خلاصهٔ اجرایی

1. **zip ورودی جدیدتر از GAP-REPORT-002 بود.** کار قبلی بیش از آنچه گزارش دوم ثبت کرده بود جلو رفته بود: `receipts.py` (۶۳۸ خط)، `events.py` (۳۲۶)، `paths.py` (۲۲۹)، `killswitch.py` lib (۳۷۱) و CLI (۴۵۹)، `tests/test_lib.py` (۸۶۹ خط، ۹۳ تست)، و **ADR-002** (تثبیت S1–S10 با D11–D18) همه موجود و سبز بودند. طبق دستور Owner، **هیچ‌کدام دوباره ساخته نشدند.**
2. **در این جلسه گام‌های ۲، ۴ (باقی)، ۵، ۶، ۷ و ۸ از نقشهٔ GAP-REPORT-002 §۶ اجرا شدند:** ۶ JSON Schema · ۵ script (`verify`, `compact`, `fsp`, `context_pack`, `reaper`) · ۷ hook · اسناد (CLAUDE.md، RECOVERY.md، CODEOWNERS، TRADEOFF-REGISTER) · ۴ workflow · و تسک end-to-end DoD.
3. **DoD خودِ VS-1 با شواهد واقعی بسته شد:** ۵ رسید زنجیره‌ای (`T-0001`..`T-0005`) در workstream `agentic-core` · `verify.py --chain` سبز · ۱۱۵/۱۱۵ تست · ۱۰/۱۰ تمرین مسیر kill switch.

**ادعایی که این گزارش نمی‌کند:** sim/ (VS-2)، Adapterها (VS-3)، Agent Cardها (VS-5) و Control Room (VS-6) هنوز وجود ندارند. شواهد `sim_evidence` این جلسه از پل D20 (ADR-003) آمده — sim-world واقعی با seed، نه سناریوهای کامل §۱۶.

---

## ۱) SYNC — وضعیت یافته‌شده در ورود (بازاندازه‌گیری، نه کپی از GAP-REPORT-002)

| بررسی | GAP-REPORT-002 گفت | واقعیت در zip این جلسه |
| --- | --- | --- |
| ADR-002 | «گام ۰ — هنوز نوشته نشده» | ✅ موجود: D11–D18، S1–S10 تثبیت‌شده |
| `receipts.py` | ۳۹۹ خط، فیلدهای §۳.۳ غایب (S2) | ✅ ۶۳۸ خط، انطباق کامل + `chain_index` (D13) |
| `events.py` | ۲۵۴ خط، `world`/`seed` غایب (S3) | ✅ ۳۲۶ خط، پارتیشن sim + watermark پایدار (D14/D18) |
| `scripts/killswitch.py` | غایب (N3) | ✅ ۴۵۹ خط، reconcile + verify drill هر ۵ مسیر |
| `tests/` | غایب (N4) | ✅ `test_lib.py` — ۹۳ تست سبز |
| `analytics/schemas/` | غایب (N1) | ❌ غایب → **در این جلسه ساخته شد** |
| `hooks/` | غایب (N2) | ❌ غایب → **در این جلسه ساخته شد** |
| scripts دیگر (`verify`، `compact`، `fsp`، `reaper`…) | غایب (N3) | ❌ غایب → **در این جلسه ساخته شد** |
| workflows | غایب (N5) | ❌ غایب → **در این جلسه ساخته شد** |
| اسناد وضعیت (N6) و receipt نمونه (N7) | غایب | ❌ غایب → **در این جلسه ساخته شد** |

نتیجهٔ SYNC: نقطهٔ ادامهٔ واقعی، گام ۲ نقشه بود، نه گام ۰. **هشدار GAP-REPORT-002 («کتابخانه به فایل‌هایی ارجاع می‌دهد که وجود ندارند») در این جلسه کامل بسته شد** — همهٔ ارجاع‌ها (`verify.py --chain/--lint-imports/--lint-clock/--repair-head`، `compact.py --rebuild`، `fsp.py bootstrap`) اکنون وجود دارند و سبزند.

## ۲) ساخته‌شده در این جلسه — با شواهد اجرا

| # | خروجی | شاهد اجرا |
| --- | --- | --- |
| 1 | `analytics/schemas/` — ۶ schema (event, receipt, state, lease, agent-card, a2a-envelope)، Draft 2020-12 + `migrations/` | هر ۶ با metaschema معتبر؛ خروجی واقعی کد strict پاس؛ دادهٔ بد رد |
| 2 | `scripts/verify.py` — ۶ دروازه: chain، events (gap scan)، schemas، agent-cards (قواعد I13/I17/§3.4)، lint-imports (acyclic + stdlib-only)، lint-clock | `--all` سبز؛ تست دستکاری receipt قرمز می‌شود |
| 3 | `scripts/compact.py` — بازسازی STATE.json از events + watermark publication (D18) + gap detection + `event.gap.detected` | `--rebuild` و پیش‌فرض سبز؛ STATE schema-valid |
| 4 | `scripts/fsp.py` — bootstrap (idempotent)، claim/heartbeat/release با fencing | claim→token1؛ double-claim رد؛ event per step |
| 5 | `scripts/reaper.py` — zombie → tombstone `crashed` + revoke با سوزاندن fencing token (succession STEP 1) + `--dry-run` | تست: lease مرده → tombstone + revoked.json |
| 6 | `scripts/context_pack.py` — تولید CONTEXT-PACK.md از وضعیت زنده | خروجی با بخش‌های Safety/Receipts/Events/FSP |
| 7 | `hooks/` — ۷ hook (رده A + pre_push) با پروتکل stdin/stdout JSON و exit code | ۱۰ تست CLI: secret در args رد · ویرایش دستی stores رد · KS ناشناختا/فعال مسدود · lease باز stop را نگه می‌دارد |
| 8 | اسناد: `CLAUDE.md` (<۴۰۰ خط) · `RECOVERY.md` (مسیر خروج غیرفنی، ۵ راه توقف) · `CODEOWNERS` (چهار مسیر انسانی) · `decisions/TRADEOFF-REGISTER.md` (۲۲ سطر، I8) | — |
| 9 | `.github/workflows/` — validate · compact (ساعتی) · heartbeat (۱۵ دقیقه: reconcile K2/K3/K5→K1 + reaper + compact) · mirror (روزانه: bundle + escrow) | ۴/۴ YAML parse؛ تمام دستورهایشان این جلسه سبز اجرا شدند |
| 10 | `tests/test_scripts.py` — ۲۲ تست CLI end-to-end روی ریشهٔ موقت | **۱۱۵/۱۱۵ سبز** (۹۳ قدیمی + ۲۲ جدید) |
| 11 | Receiptهای زنجیره‌ای `T-0001`..`T-0005` + رویدادهای متناظر | `verify.py --chain` سبز، head_index=4 |
| 12 | `ADR-003` (D19–D22) · این گزارش · `artifacts/sim/T-000{1,4}/` (پل D20) | — |

## ۳) DoD خودِ VS-1 (BUILD-SPEC §۱۷) — جدول اثبات

| معیار DoD | شاهد | وضعیت |
| --- | --- | --- |
| یک تسک ساختگی از CLAIM تا HANDOFF | T-0005: claim token1 → اجرا → verify → receipt `complete` → HANDOFF | ✅ |
| receipt با `status: complete` | `receipts/2026/07/T-0005.json` — verification سبز، rollback tested | ✅ |
| زنجیرهٔ معتبر | `verify.py --chain` → GREEN، ۵ رسید، index 0..4 بدون شکاف | ✅ |
| `verify.py --chain` سبز | همان | ✅ |

## ۴) انحراف/تصمیم جدید (ثبت‌شده در ADR-003، نه سکوت)

- **D19** رویداد hookهای پرتکرار فقط روی deny (حجم audit قابل‌کنترل).
- **D20** پل sim-evidence پیش از VS-2: sim-world واقعی با `seed=1337`، نه سناریوهای §۱۶. بازنشستگی خودکار با VS-2.
- **D21** تفکیک `CODE_ROOT`/artifact root در verify.py (تست CLI باگ کشف آثار را گرفت).
- **D22** pre_push class-B فعلاً `unittest + verify --all`؛ جای sim/contract tests با guard در validate.yml رزرو شده.

## ۵) فهرست قطعی «شروع‌نشده» پس از این جلسه

| # | مورد | اسلایس | یادداشت |
| --- | --- | --- | --- |
| N8 | `sim/` کامل: clock.py (وجود دارد در lib) · world.py · chaos.py · report.py · `fakes/` (۹ adapter) · `scenarios/*.yaml` (۱۴ سناریو) · `scripts/sim.py` | **VS-2** | گام بعدی. پیش‌نیازها آماده: VirtualClock ✅، paths با `MARZNESHIN_OPS_ROOT` ✅، پارتیشن sim ✅، seed در event ✅ |
| N9 | `adapters/` (۹ adapter + contract test + fake) | VS-3 | Adapter بدون fake merge نمی‌شود (§۴) |
| N10 | `agents/cards/` — ۷ Agent Card Tier 0 | VS-5 | schema و CI قواعد (I13/I17) از VS-1 آماده است |
| N11 | `skills/` — ۱۱ SKILL.md با هدر §۷.۳ | VS-5+ | الگوهای gstack (qa/review/freeze/ship) به‌عنوان مرجع ساختار بررسی شد |
| N12 | `mcp/`، `plugins/marzneshin-ops/` | VS-3+ | ۱۲ command با schema خروجی |
| N13 | `growth/`، `analytics/{events,models,dashboards}/`، `security/`، `configs/`، `infra/` | VS-7+ | — |
| N14 | ۷ workflow باقی CI (security، release، notify، experiment، succession، sim-nightly، a2a-dispatch) | VS-3..VS-11 | — |
| N15 | `gateway/` | VS-12 | **عمداً ممنوع** (§۱.۲) |
| N18 | Moxt Workflow «Control Room» + AI Teammates | VS-6/VS-3 | در این workspace ساخته می‌شود، نه در repo |

## ۶) اقدام‌های باز برای Owner انسانی (بدون تغییر از ADR-002 + یک مورد جدید)

| # | مورد | اثر |
| --- | --- | --- |
| O1 | تأیید قیمت واقعی مدل‌ها (D17) | `forecast()` تقریبی می‌ماند |
| O2 | MASTER-PLAN v4.0 یا پذیرش بازنویسی قرارداد آزمایش | VS-9/VS-10 مسدود؛ VS-2..VS-8 آزاد |
| O3 | GitHub App / fine-grained token + repo واقعی (A1) | push/Actions واقعی فعال شود؛ همه‌چیز push-ready است |
| O4 | کانال هشدار خارج از باند (A4) | dead-man switch در VS-4 |
| **O5** | **جایگذاری venv/CI: `jsonschema` + `pyyaml`** | strict validation در CI به آن‌ها وابسته است (validate.yml نصب می‌کند) |

## ۷) وضعیت

```plain
SLICE: VS-1 | STATUS: green — DoD بسته شد با شواهد (۵ receipt زنجیره‌ای، chain سبز، ۱۱۵/۱۱۵ تست، ۱۰/۱۰ drill)
DONE:  ۶ schema · ۵ script · ۷ hook · ۴ workflow · اسناد ۴گانه · ۲۲ تست CLI جدید
       · receiptهای T-0001..T-0005 · ADR-003 · شناسایی و رفع ۳ باگ واقعی در این جلسه
       (ristrict-date.today در ۳ اسکریپت، artifact discovery در verify.py، forecast:None در compact.py)
NEXT:  VS-2 Simulation Harness طبق §۱۶: scripts/sim.py + sim/{world,chaos,report}.py
       + fakes/ + ۶ سناریوی اول (node_outage، payment_provider_down، agent_crash_mid_task،
       lease_expiry، cost_spike، prompt_injection) — DoD: ۷۲ ساعت مجازی < ۶۰ ثانیه با seed
BLOCKERS: هیچ‌کدام برای VS-2 (صفر credential لازم دارد) · O1–O5 برای اسلایس‌های بعدی
RECEIPTS: receipts/2026/07/T-000{1..5}.json — زنجیرهٔ agentic-core، head index 4
TOKENS: این جلسه: ساخت کامل VS-1 (ادامه‌دهنده، نه بازساز — zip جدیدتر از GAP-REPORT-002 بود)
```
