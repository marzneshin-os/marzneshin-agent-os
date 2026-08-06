# ADR-001 — تصمیم‌های بنیادی معماری

- **وضعیت:** Accepted
- **تاریخ:** 2026-07-28
- **تصمیم‌گیرنده:** Owner فنی (Claude Opus 5) — طبق مجوز BUILD-SPEC §۰: «جایی که سند ساکت است، تصمیم بگیر، تصمیم را ثبت کن و ادامه بده»
- **ورودی:** BUILD-SPEC v1.0 · GAP-REPORT-001 · اندازه‌گیری واقعی محیط
- **دامنه:** VS-1 تا VS-12

---

## D1 — Transport سه‌لایه؛ A2A Gateway از مسیر بحرانی خارج می‌شود

**زمینه.** BUILD-SPEC §۵ یک Gateway اجباری (FastAPI + Postgres + Redis + mTLS) تعریف می‌کند که همهٔ ترافیک L3 از آن می‌گذرد، اما بستر اجرای آن را تعریف نمی‌کند. محیط سنجیده‌شده Docker/Postgres/Redis ندارد و sandbox بین جلسات پایدار نیست.

**تصمیم.**
- `T1 git-transport` — منبع حقیقت و baseline. task = فایل JSON در `state/a2a/inbox/{agent}/`، trigger با GitHub Actions. همیشه در دسترس، audit ذاتی، هزینهٔ زیرساخت صفر.
- `T2 moxt-transport` — مسیر سریع بومی. task = Task در Moxt Workflow؛ assign به AI Teammate آن ایجنت را trigger می‌کند. بدون سرور، با مسیر تأیید انسانی بومی.
- `T3 http-transport` — Gateway §۵ به‌عنوان **بهینه‌سازی latency**، اختیاری، VS-12.

**قوانین اجباری.** هیچ قابلیت ایمنی‌ای فقط روی T3 زنده نیست · health check هر ۶۰ثانیه، ۳ خطای پیاپی → fallback خودکار به T1 · هر سه transport یک envelope مشترک (§۳.۵) دارند تا جابه‌جایی بی‌هزینه باشد.

**پیامد.** SPOF حذف شد. VS-1..VS-5 بدون هیچ زیرساخت خارجی تحویل‌شدنی شدند. هزینه: latency پایه ۳۰–۹۰ ثانیه در T1 — که برای حلقهٔ ۳۰ دقیقه‌ای §۱۲.۱ بی‌اثر است.

**رد شد.** *Gateway اجباری از روز اول* — SPOF، هزینهٔ عملیاتی، و مسدودکنندهٔ VS-1.

---

## D2 — GitHub تنها SSoT می‌ماند؛ Moxt سطح کاری و کنترل است

**تصمیم.** I1 دست‌نخورده. GitHub = SSoT. Moxt workspace = سطح ساخت، Control Room و اجرای ایجنت. Moxt → GitHub تنها با commit صریح از طریق `adapters/github`. ClickUp (اگر فعال شود) mirror فقط‌خواندنی، با دو استثنای مجاز §۹.۵ (فیلد Approval و وضعیت Kill Switch).

**دلیل.** git در workspace مصنوعی است و commit بلاک شده؛ پس Moxt نمی‌تواند SSoT باشد. اما Moxt چیزی دارد که GitHub ندارد: trigger بومی ایجنت، مسیر تأیید انسانی، و cron/webhook بدون host.

---

## D3 — Control Room بومی Moxt؛ ClickUp اختیاری و پشت adapter

**تصمیم.** Control Room اولیه = Moxt Workflow با statusهای §۹.۳ و فیلدهای §۹.۲. ClickUp پشت `adapters/clickup` با همان interface §۴ می‌ماند و در صورت ارائهٔ token فعال می‌شود.

**دلیل.** حذف وابستگی به SaaS پرداختی از مسیر Governance؛ assign کردن Task در Moxt هم‌زمان mirror و trigger است. مهم‌تر: kill switch نباید روی یک token خارجی سوار باشد (G3).

**Trade-off ثبت‌شده.** Moxt Workflow داشبورد تحلیلی ClickUp را ندارد → VS-10 با Mini App + Grafana پوشش می‌دهد.

---

## D4 — حذف `seq` سراسری؛ پارتیشن نوشتن به‌ازای هر actor

**تصمیم.** `event_id` = ULID · `actor_seq` یکنواخت به‌ازای هر actor · ترتیب علّی از `causation_id` · مسیر رویداد `state/events/{YYYY-MM-DD}/{actor}.ndjson`.

**دلیل.** CAS سراسری روی git زیر ۵ نویسندهٔ موازی تبدیل به retry storm می‌شود، و ترتیب کلی هرگز مورد نیاز نبود. با یک نویسنده به ازای هر فایل، merge conflict **ساختاراً ناممکن** می‌شود.

**تعمیم.** همین قاعده (یک نویسنده به ازای هر مسیر) با `owns` در Agent Card ترکیب و در `hooks/pre_tool.py` اجبار می‌شود.

---

## D5 — Fail-closed برای همهٔ کنترل‌های ایمنی

**تصمیم.** kill switch پنج‌مسیره (فایل repo، GitHub variable، Moxt Workflow، CLI، خودکار). قانون: اگر وضعیت kill switch از **هیچ** مسیر معتبری با timestamp تازه‌تر از ۱۵ دقیقه خوانده نشود → هر عملیات با blast radius بالاتر از L3 **متوقف** می‌شود. «نمی‌دانم» = «متوقف شو».

همین اصل روی: probe سالم موجود نیست → ارتقای canary ممنوع · budget ledger خوانده نمی‌شود → فقط عملیات L4 · lease قابل تأیید نیست → نوشتن ممنوع.

**پیامد.** در قطعی شبکه سیستم متوقف می‌شود نه اینکه کور ادامه دهد. `--verify` شبانه هر پنج مسیر را عملاً تست می‌کند.

---

## D6 — Simulation Harness یک اسلایس درجه‌یک است (VS-2)

**تصمیم.** `sim/` با ساعت مجازی، fake همهٔ Adapterها، سناریوهای YAML و تزریق خطای seed-دار. **هیچ کد نویی وارد مسیر production نمی‌شود مگر ابتدا در `sim/` سبز شود.** `seed` در هر receipt ثبت می‌شود.

**دلیل.** DoD‌های VS-10 (۷۲ ساعت)، تست Chaos §۱۶ و cold restore drill §۱۱.۲ بدون آن قابل اثبات نیستند — و جایگزین واقعی‌شان تست روی کاربران Marzneshin است.

---

## D7 — Two-key = دو تبار مستقل + یک نقش خصمانه

**تصمیم.** «مستقل» تعریف عملیاتی: مدل یا prompt-lineage متفاوت + دسترسی به شواهد خام (نه خروجی کلید اول) + وظیفهٔ صریح **رد کردن**. یک `Adversarial Reviewer` در Tier 0 اضافه می‌شود. CODEOWNERS انسانی به چهار مسیر محدود می‌شود: `configs/pricing/**`, `**/ToS*`, `infra/terraform/**`, `security/iam/**`.

**دلیل.** Workspace یک انسان دارد؛ two-key به شکل §۱۱.۲ برقرارشدنی نیست. یک ایجنت با همان مدل و همان context کلید دوم نیست — آینه است.

---

## D8 — ترکیب Tier 0 و ترتیب اسلایس‌ها بازچینی می‌شود

**تصمیم.** Tier 0 از ۵ به ۷: + **Handoff Guardian** (از Tier 1؛ قانون آهنین ۳ از VS-1 لازم است) + **Adversarial Reviewer**. `Analytics Engineer` به Tier 1. ترتیب اسلایس‌ها طبق GAP-REPORT §G15: Simulation به VS-2، Continuity + Kill Switch به VS-4 (قبل از هر تماس با production)، Control Room به VS-6، Config Pipeline به VS-7.

**دلیل.** ترتیب v1.0 روی کاربران واقعی config منتشر می‌کرد **قبل از** اثبات succession و rollback. این وارونگی ریسک است.

---

## D9 — Idempotency سه‌کلاسه · Receipt پنج‌وضعیته و زنجیره‌ای · Taint tracking

**تصمیم (فشرده، جزئیات در GAP-REPORT G4/G5/G10/G18).**
- idempotency به‌ازای هر capability: `forever | scoped(ttl) | none`.
- `receipt.status ∈ {complete, failed, abandoned, crashed, superseded}` + reaper که tombstone می‌نویسد. KPI: «۱۰۰٪ تسک‌ها receipt دارند» + `crash_rate < 2%`.
- `receipt.prev_receipt_hash` به‌ازای هر workstream → زنجیرهٔ ضددستکاری، تأیید در CI.
- `input_provenance` با سطوح `owner|internal|untrusted`؛ هر ابزار جهش‌دهنده با پارامتر مشتق از `untrusted` سقف L1 می‌گیرد.

---

## D10 — زبان و مالکیت اسناد

**تصمیم.** اسناد استراتژی و spec به **فارسی** (پیوستگی با MASTER-PLAN و BUILD-SPEC v1.0) · کد، نام فایل، پیام commit، schema و لاگ به **انگلیسی** · گفت‌وگوی جلسه با Owner به انگلیسی.

---

## پیامدهای منفی پذیرفته‌شده (به TRADEOFF-REGISTER منتقل می‌شوند)

| تصمیم | هزینهٔ پذیرفته‌شده | مهار |
|---|---|---|
| D1 T1 baseline | latency ۳۰–۹۰s | T2 برای مسیرهای حساس به latency؛ T3 در VS-12 |
| D3 Moxt Control Room | بدون داشبورد تحلیلی آماده | Mini App در VS-10 |
| D4 حذف total order | استدلال دربارهٔ ترتیب سخت‌تر | ULID + زنجیرهٔ causation + تست replay |
| D5 fail-closed | توقف‌های کاذب در قطعی شبکه | پنج مسیر مستقل؛ پنجرهٔ ۱۵ دقیقه؛ verify شبانه |
| D6 sim اجباری | هزینهٔ ساخت پیش‌پرداخت (~یک اسلایس) | همان هزینه در VS-4..VS-11 بازیافت می‌شود |
| D7 بازبین خصمانه | هزینهٔ توکن بیشتر به‌ازای هر تغییر بحرانی | فقط روی مسیرهای بحرانی، نه همهٔ کارها |
