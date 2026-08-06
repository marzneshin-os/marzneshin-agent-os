# ADR-005 — اجرای اسلایس VS-3: گذرگاه A2A روی T1/T2، مسیریابی با fallback، و قراردادهای وابسته

- **وضعیت:** Accepted
- **تاریخ:** 2026-07-30
- **تصمیم‌گیرنده:** momo (جلسهٔ S-2026-07-30-VS3) — طبق مجوز BUILD-SPEC §۰ و تفویض Owner («تصمیم‌های فنی را خودت بگیر و گزارش بده»)
- **ورودی:** BUILD-SPEC v2.0 §۳.۵/§۵/§۶/§۹/§۱۷ · ADR-001..004 · GAP-REPORT-004
- **دامنه:** `scripts/lib/a2a.py` · `scripts/a2a.py` · `agents/registry.json` · `scripts/lib/{policy,events,paths,verify}.py` · `sim/**` · `.github/workflows/a2a-dispatch.yml` · Moxt Workflow «Control Room» در این workspace

---

## D27 — Registry به‌صورت JSON است، نه YAML

**زمینه.** §۶ `agents/policies/rules.yaml` را برای قواعد policy می‌گوید، اما registry (نگاشت ایجنت→capability→transport) را **lib در runtime** می‌خواند و lib باید stdlib-only بماند (G9 / lint-imports). YAML parser به lib نمی‌آید.

**تصمیم.** `agents/registry.json` (با توضیح مرجع در `note`). قواعد ریسک همچنان در `policy.py::RISK_MATRIX` زندگی می‌کنند؛ registry فقط دادهٔ مسیریابی/ظرفیت است. وقتی VS-5 کارت‌های کامل ایجنت (`agents/cards/`) را آورد، registry به خوانندهٔ کارت‌ها سوئیچ می‌کند و فیلدهای autonomy/owns از کارت می‌آیند.

**رد شد.** *YAML برای registry + parse در لایهٔ script* — دو منبع حقیقت برای یک داده؛ خواندن ناسازگار در مسیر داغ.

## D28 — پل T2 در production: dispatch record روی دیسک + assignment روی Moxt Workflow

**زمینه.** §۵.۲: «task = یک Task در Moxt Workflow با envelope در بدنه؛ assign به AI Teammate = trigger». lib نمی‌تواند network I/O کند (G9)، پس assignment واقعی را خودِ پلتفرم (ایجنت اپراتور با ابزارهای Moxt) انجام می‌دهد، نه lib.

**تصمیم.** `FileT2Client`: نوشتن record در `state/a2a/t2/{task_id}.json` (envelope + moxt_ref + status) و سلامت = تازگی `state/a2a/t2/health.json` (آستانهٔ ۳۰۰ ثانیه؛ کهنه/غایب = unavailable → fail-closed به T1). پردازش با `a2a.py process-t2 --task-id …` از همان مسیر audit (outbox → processed) عبور می‌کند؛ نتیجهٔ پلتفرم (تغییر status + کامنت، §۵.۲) در Control Room ثبت و سپس به audit store آینه می‌شود (D34).

**رد شد.** *کلاینت HTTP از داخل lib به API پلتفرم* — نقض G9 و تزویج حیات bus به یک endpoint خارجی.

## D29 — fallback درون‌ارسالی: شکست deliver روی T2 = همان envelope روی T1

**زمینه.** §۵ حاکم: «Gateway باید بتواند بمیرد و سیستم با تنزل latency، نه توقف، ادامه دهد». نسخهٔ اول پیاده‌سازی تا آستانهٔ ۳ شکست، task را fail برمی‌گرداند — یعنی توقفِ جریان کار به‌جای تنزل.

**تصمیم.** در `a2a.send`، هر Exception از `T2.deliver` → ثبت شکست در health + نوشتن همان envelope (بدون هیچ تغییر محتوا، §۳.۵) در T1 inbox. رویداد `transport.degraded` دقیقاً در آستانهٔ ۳ شکست پیاپی صادر می‌شود. task هرگز به‌خاطر مردن مسیر سریع گم نمی‌شود.

**پیامد.** retry آگاهانهٔ اپراتور با `retry_of`/`attempt` در envelope هنوز هم معنا دارد (شکست‌های غیرtransport مثل policy deny).

## D30 — health probe در حالت degraded متوقف نمی‌شود (half-open)

**زمینه.** باگ واقعیِ یافته‌شده در همان جلسه: `choose_route` در حالت degraded بی‌درنگ T1 برمی‌گرداند و healthz را صدا نمی‌زد ⇒ شمارندهٔ موفقیت‌های پیاپی هرگز به ۵ نمی‌رسید ⇒ قاعدهٔ بازگشت §۵.۵ مرده بود.

**تصمیم.** probe همیشه اجرا می‌شود (ارزان است)، حتی در degraded؛ نتیجه در شمارنده‌ها ثبت می‌شود. بازگشت دقیقاً با ۵ موفقیت پیاپی (hysteresis ضد flapping). تست واحد مسیر degrade→probe→restore را پوشش می‌دهد و سناریوی `a2a_fallback` آن را end-to-end ثابت می‌کند.

## D31 — افزودن prefixهای VS-3 به RISK_MATRIX

**زمینه.** `policy.classify` برای capability ناشناخته default-deny (L0) می‌دهد (D5). capabilityهای bus باید طبقه‌بندی شوند وگرنه هیچ dispatchای از gate عبور نمی‌کند.

**تصمیم.** `qa.*` و `probe.*` → `read_analyze` (خروجی verdict/نمونه، غیرجهش‌دهنده) · `a2a.*` → `internal_artifact` · `policy.evaluate` → `read_analyze` · `config.*` → `reversible_config` (آینهٔ `flag.*`). registry می‌تواند idempotency را **سخت‌گیرانه‌تر** کند (probe.echo: scoped/3600) ولی هرگز شل‌تر نه (قاعدهٔ `idempotency_spec`).

## D32 — تفکیک artifact gate روی `state/a2a/`

**زمینه.** `_iter_artifact_files` (VS-1) همهٔ `state/a2a/**/*.json` را envelope فرض می‌کرد؛ VS-3 فایل‌های غیرenvelope ساخت (recordهای نتیجه، idem store، t2 records، health) ⇒ verify قرمز شد.

**تصمیم.** inbox → schema `a2a-envelope` · outbox/processed → schema جدید `a2a-result` · `idem/`، `t2/`، `transport_health.json` → حالت داخلی bus (مثل events/ و budget/) و خارج از gate. قاعده: هر **artifact** schema دارد؛ هر **runtime state** لزوماً نه.

## D33 — در sim، kill switch با وضعیت clear بذر می‌شود + بازیگر heartbeat

**زمینهٔ کشف.** root موقت sim نه KILL داشت نه heartbeat ⇒ همهٔ gateهای policy پس از ۳ تیک مجازی (۹۰۰ ثانیه) fail-closed رد می‌شدند. سناریوهای VS-2 هرگز ALLOW لازم نداشتند (config-engineer فقط idempotency key می‌ساخت؛ injection-tester دقیقاً deny را تست می‌کرد) — اولین مصرف‌کنندهٔ ALLOW در sim، گذرگاه A2A بود.

**تصمیم.** `scripts/sim.py` هنگام bootstrap سناریو `killswitch.reconcile(external=[], sources=["sim:bootstrap"])` می‌زند (معادل وضعیت production با heartbeat workflow سالم) و `DispatcherActor` هر ۲ تیک `touch_heartbeat` می‌کند — آینهٔ workflow پانزده‌دقیقه‌ای §۸ در زمان مجازی. این تضعیف نیست: شبیه‌سازیِ همان مؤلفه‌ای است که prod برای تازگی K1 به آن وابسته است.

**صدق مرز.** مسیر fail-closed همچنان در `killswitch.py verify` (۱۰/۱۰) و سناریوی `killswitch_unreadable` (از ۸ سناریوی باقی §۱۶) تمرین می‌شود.

## D34 — آینهٔ نتیجهٔ T2 از پلتفرم به audit store

**زمینه.** §۵.۲: «result = تغییر status + کامنت با اشاره به receipt». در اجرای واقعی این جلسه، pipelineِ triggerشدهٔ qa-gate نتیجه را روی Task پلتفرم گذاشت (کامنت + Done) و نوشتن‌های sandbox آن session با تأخیر sync می‌شدند.

**تصمیم.** سمت orchestrator پس از مشاهدهٔ نتیجه روی پلتفرم، record نهایی (outbox/processed/idem/t2) را با `reported_via` و moxt_ref آینه می‌کند و رویداد `a2a.completed` می‌زند. منبع حقیقتِ *اجرای* T2 پلتفرم است؛ منبع حقیقتِ *audit* repo — این دقیقاً تقسیم‌کار §۹.۵ (I1) است.

**پیامد پذیرفته‌شده.** پنجرهٔ کوتاه «queued در repo، completed روی پلتفرم» — با heartbeat و رویداد آینه بسته می‌شود؛ در TRADEOFF-REGISTER (T23) ثبت شد.

---

## پیامدهای منفی پذیرفته‌شده (به TRADEOFF-REGISTER رفتند)

| # | تصمیم | هزینه | مهار |
| --- | --- | --- | --- |
| T23 | نتیجهٔ T2 ابتدا روی پلتفرم، سپس آینه به repo | پنجرهٔ ناسازگاری کوتاه | heartbeat + رویداد آینه + idem store |
| T24 | heartbeat در sim توسط بازیگر dispatcher تازه می‌شود | یک بازیگر با دو نقش | جدا کردن بازیگر heartbeat در VS-4 اگر سناریو پیچیده شد |
