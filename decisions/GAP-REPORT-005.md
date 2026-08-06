# GAP-REPORT-005 — بستن VS-3 (A2A over T1/T2) با تمرین واقعی روی هر دو transport

> **مرجع:** BUILD-SPEC v2.0 §۳.۵/§۵/§۶/§۹/§۱۷ · ADR-001..005 · GAP-REPORT-004
> **نویسنده:** momo (جلسهٔ S-2026-07-30-VS3) · **تاریخ:** 2026-07-30
> **وضعیت:** **VS-3 بسته شد.** DoD با یک task واقعی روی **هر دو** transport + idempotency اثبات‌شده + fallback خودکار T2→T1 ارضا شد — روی sim (۲۱/۲۱) و روی پلتفرم واقعی Moxt (T2 با assignment trigger زنده). اسلایس بعدی: **VS-4 (Continuity + Kill Switch)**.

---

## ۰) خلاصهٔ اجرایی

1. **گذرگاه A2A کامل ساخته شد** طبق §۳.۵/§۵: envelope مشترک · registry · Policy Engine (موجود از VS-1، با prefixهای جدید D31) · سه کلاس idempotency روی دیسک · مسیریاب با health + hysteresis §۵.۵ · T1 فایل‌محور (inbox→outbox→processed، I17) · T2 روی Moxt Workflow واقعی.
2. **DoD اسلایس با شواهد واقعی بسته شد:** task `A2A-01KYSHGH38PNZ3AR47F15NZNZV` (orchestrator→qa-gate، `qa.gate.run`) روی **T2** از Control Room مoxt با assignment trigger اجرا و GREEN شد (کامنت نتیجه + Done) · روی **T1** task `A2A-01KYSHE1E5J4F0D0MAKFDPM0JF` با verdict green (۶ check) تکمیل شد · ارسال مجدد همان envelope = replay بدون اجرای دوباره (idem store) · fallback T2→T1 در سناریوی `a2a_fallback` روی ۳ seed با score ۱٫۰.
3. **سه باگ واقعی در همین جلسه کشف و رفع شد:** (الف) مسیر بازگشت §۵.۵ بدون probe در degraded مرده بود (D30) · (ب) سیاست fail-closed در sim بدون بذر KS/heartbeat همهٔ ALLOWها را می‌کشت (D33) · (ج) T2-delivered taskها در sim drain نمی‌شدند (sim T2 ناقص بود — با dispatch record یکسان‌سازی شد).

**ادعایی که این گزارش نمی‌کند:** T1 dispatcher روی GitHub Actions واقعی اجرا نشده (O3 — token؛ workflow `a2a-dispatch.yml` push-ready است) · Agent Cardهای کامل (VS-5) هنوز نیامده‌اند · `agents/cards/` خالی است · ۸ سناریوی باقی §۱۶ برای اسلایس‌های بعدی‌اند.

---

## ۱) SYNC — وضعیت ورود

جلسه با پروتکل §۰ باز شد: `fsp status` (زنجیره سالم، ۶ رسید) · claim توکن ۴ · kill switch با reconcile به RUNNING. VS-2 بسته و سبز از جلسهٔ قبل. zip/state دست‌نخورده باقی‌مانده از VS-2 حفظ شد؛ هیچ بخش ساخته‌شده‌ای بازسازی نشد.

## ۲) PLAN (۷ گام)

1. `agents/registry.json` + `scripts/lib/a2a.py` (envelope، registry، idem store، router) ✅
2. `scripts/a2a.py` CLI (send/process/process-t2/status/verify + handlerهای واقعی) ✅
3. `.github/workflows/a2a-dispatch.yml` (T1 dispatcher + policy gate اجباری §۶) ✅
4. sim: `DispatcherActor` + `SimT2Client` + سناریوی `a2a_fallback.yaml` ✅
5. تست: `tests/test_a2a.py` (۱۴ تست) + به‌روزرسانی suite (۲۱ PASS) ✅
6. T2 واقعی: Control Room workflow + dispatch با assignment trigger ✅
7. دروازه‌ها + رسیدها + اسناد ✅

## ۳) ساخته‌شده — با شاهد اجرا

| # | خروجی | شاهد |
| --- | --- | --- |
| 1 | `scripts/lib/a2a.py` (۵۵۰ خط) — envelope/schema، registry، idem store، router §۵.۵، T1/T2 transports، state machine با event per transition | تست‌های واحد ۱۴/۱۴ |
| 2 | `scripts/a2a.py` (۲۹۰ خط) — ۵ فرمان؛ handler واقعی `qa.gate.run` (اجرای verify.py) و `probe.echo` | `a2a.py verify` سبز؛ drillهای T1/T2 |
| 3 | `agents/registry.json` — ۳ ایجنت، ۷ capability، ترجیح transport، overrides idempotency | gate `a2a.py verify` |
| 4 | `.github/workflows/a2a-dispatch.yml` — path filter روی inbox + policy gate + drain + commit نتیجه | YAML parse سبز (push-ready، O3 برای اجرای واقعی) |
| 5 | `sim/scenarios/a2a_fallback.yaml` + `DispatcherActor` + `SimT2Client` | **۳/۳ seed سبز، score ۱٫۰، checks 11/11** |
| 6 | `tests/test_a2a.py` — envelope، fail-closed registry، replay، TTL expiry، fallback+restore، CLI | ۱۴/۱۴ سبز |
| 7 | **Moxt Workflow «Control Room»** — ۹ status مطابق §۹.۳ + ۱۴ transition + Task#1 | Task#1 با pipeline trigger اجرا و Done شد |
| 8 | schema جدید `a2a-result` + تفکیک artifact gate (D32) | `verify --all` سبز (20 artifact) |
| 9 | بذر KS در sim + بازیگر heartbeat (D33) | policy ALLOW در sim ممکن شد |

## ۴) DoD خودِ VS-3 (BUILD-SPEC §۱۷) — جدول اثبات

| معیار DoD | شاهد | وضعیت |
| --- | --- | --- |
| یک task واقعی میان دو ایجنت روی T1 | `state/a2a/processed/qa-gate/A2A-01KYSHE1E5…json` — verdict green، ۶ check واقعی از verify.py --all | ✅ |
| همان روی T2 | Moxt Control Room Task#1: assignment → pipeline `PCWBC3672RM2EBF9` → کامنت verdict GREEN → Done؛ mirror در `state/a2a/processed/qa-gate/A2A-01KYSHGH38….json` | ✅ |
| با audit | eventهای `policy.evaluated`/`a2a.dispatched`/`a2a.received`/`a2a.completed` در پارتیشن prod با correlation_id | ✅ |
| idempotency اثبات‌شده (تکرار = بدون اجرای دوباره) | resend همان envelope ⇒ `replayed: true` (store حالت queued/completed برمی‌گرداند) · تست واحد TTL/replay · sim: `duplicate_work=0` با ۷۱ replay روی هر seed | ✅ |
| fallback خودکار T2→T1 | `a2a_fallback`: moxt down در تیک ۱۲ ⇒ `transport.degraded` ⇒ همهٔ ترافیک روی T1 ⇒ بازیابی با ۵ health سبز (hysteresis) ⇒ `a2a_completed=145`، `a2a_failed=0` × ۳ seed | ✅ |

## ۵) تغییرات وابسته (شفاف، نه پنهان)

- `policy.py` RISK_MATRIX: ۵ prefix جدید (D31) — بدون آن هیچ dispatchای رد می‌شد.
- `events.py` + `event.schema.json`: ۸ نوع رویداد جدید a2a/transport (قاعدهٔ «همان commit» رعایت شد).
- `scripts/verify.py`: artifact gate تفکیک شد (D32) — schema `a2a-result` جدید.
- `scripts/sim.py`: بذر KS هنگام bootstrap سناریو + کپی registry به root موقت (D33).
- `test_sim.py`: انتظار ۲۱ PASS (۷ سناریو × ۳ seed).

## ۶) فهرست «شروع‌نشده» پس از این جلسه

| # | مورد | اسلایس | یادداشت |
| --- | --- | --- | --- |
| N9 | adapterهای *واقعی* (۹ adapter روی sandbox) | VS-4+ | پروتکل + قرارداد + ۹ fake سبز‌اند؛ fixture vault (D23) آماده · O3 |
| N10 | `agents/cards/` — ۷ Agent Card Tier 0 | VS-5 | registry جای موقت آن‌هاست (D27) |
| N11 | `skills/` — ۱۱ SKILL.md (الگوی gstack) | VS-5+ | نگاشت gstack در GAP-REPORT-004 §۶ |
| N18 | Control Room کامل §۹ (Views، فیلدهای native، sync دوطرفهٔ محدود) | VS-6 | اسکلت workflow + ۹ status + ۱۴ transition ساخته شد؛ Task#1 اولین mirror واقعی |
| — | ۸ سناریوی باقی §۱۶ | VS-4..VS-7 | killswitch_unreadable مرتبط‌ترین به VS-4 است |
| — | watcher روی Control Room | VS-4/VS-6 | heartbeat/dead-man switch |

## ۷) اقدام‌های باز Owner

O1 قیمت مدل‌ها · O2 MASTER-PLAN (فقط VS-9/10) · **O3 GitHub token — حالا مسیر T1 واقعی (a2a-dispatch.yml) و push را هم محدود می‌کند** · O4 کانال OOB واقعی (VS-4) · O5 حل‌شده محلی (venv).

## ۸) وضعیت

```plain
SLICE: VS-3 | STATUS: green — DoD بسته شد با تمرین واقعی روی T1 و T2 + ۲۱/۲۱ sim + ۱۴۶/۱۴۶ تست
DONE:  گذرگاه A2A کامل (envelope/registry/router/idem/T1/T2) · CLI + ۵ فرمان · a2a-dispatch.yml
       · سناریوی a2a_fallback (۳/۳ seed) · ۱۴ تست جدید · Control Room workflow + Task#1 Done
       · ADR-005 (D27–D34) · ۳ باگ واقعی کشف و رفع شد (probe در degraded، بذر KS در sim، drain T2)
NEXT:  VS-4 (Continuity + Kill Switch): succession workflow، dead-man switch، ۵ مسیر kill switch در sim،
       cold restore با معیار چهارگانهٔ §۱۱.۲، سناریوی killswitch_unreadable
BLOCKERS: O3 (GitHub token) برای T1 واقعی/push · O4 برای dead-man switch واقعی (VS-4)
RECEIPTS: receipts/2026/07/T-000{1..8}.json — زنجیرهٔ agentic-core، head index 7
TOKENS: این جلسه: ساخت کامل VS-3 + اولین dispatch واقعی T2 روی پلتفرم
```
