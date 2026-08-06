# ADR-003 — اجرای اسلایس VS-1: hookها، CI، و پل shibeh-sazi پیش از VS-2

- **وضعیت:** Accepted
- **تاریخ:** 2026-07-30
- **تصمیم‌گیرنده:** Owner فنی (ادامهٔ پیاده‌سازی پس از مهاجرت workspace دوم) — طبق مجوز BUILD-SPEC §۰
- **ورودی:** BUILD-SPEC v2.0 · ADR-001 · ADR-002 · GAP-REPORT-002 (گام‌های ۲–۸)
- **دامنه:** `hooks/**` · `scripts/verify.py` · `.github/workflows/**` · `receipts/**` · `artifacts/sim/**`

---

## D19 — رویداد hookهای پرتکرار فقط روی deny ثبت می‌شود

**زمینه.** §۷.۲: «هر hook خروجی JSON می‌دهد و خودش event ثبت می‌کند». اما `pre_tool` و `post_tool` روی **هر** فراخوان ابزار آتش می‌شوند. ثبت یک event به‌ازای هر allow یعنی هزاران رخداد بی‌ارزش در روز در پارتیشن production — هزینهٔ compaction بالا می‌رود و سیگنال واقعی (denyها) در نویز غرق می‌شود.

**تصمیم.** `pre_tool`/`post_tool` فقط روی **deny/block** رویداد ثبت می‌کنند (`policy.denied`). allowها در خودِ tool log زیرساخت باقی می‌مانند. hookهای کم‌تکرار (session_start، task_complete، stop، pre_commit، pre_push) همچنان همیشه ثبت می‌کنند، چون هر فراخوانشان یک مرز معنادار است.

**دلیل.** ارزش audit در deny است: «چه کسی، چه چیزی، چرا رد شد» همان چیزی است که بعداً باید قابل بازیابی باشد. یک رویداد allow در هر کلیک ابزار، audit را نه قوی‌تر که ناخواناتر می‌کند — همان الگوی «هشدار کاذب → خاموش شدن در هفتهٔ دوم» که G5 برای receipt coverage تشخیص داد.

**پیامد پذیرفته‌شده.** مسیر allow در event log نیست. اگر در VS-3 (A2A) معلوم شد audit کامل لازم است، یک رویداد خلاصهٔ تجمیعی (hourly rollup) به compact اضافه می‌شود، نه event-per-call.

**رد شد.** *ثبت همهٔ allowها* — حجم event را منفجر می‌کند و deny را دفن می‌کند.

---

## D20 — پل شواهد sim پیش از VS-2 (spine زیر ساعت مجازی)

**زمینه.** I11: «هیچ کد نویی بدون سبز شدن در `sim/` به production نمی‌رود» و `receipts.py` این را مکانیکی اجبار می‌کند (`sim_evidence` برای هر تغییر کد/کانفیگ). اما `sim/` خودش تحویل VS-2 است — یعنی کدهای VS-1 (که sim را *می‌سازند*) با قاعده‌ای که هنوز زیرساختش نیست سنجیده می‌شوند. این تناقض ظاهری، در طراحی §۱۷ حل شده: ترتیب اسلایس‌ها آگاهانه VS-1 را قبل از sim گذاشته و DoD خودِ VS-1 شواهد sim نمی‌خواهد. با این حال receiptهای `complete` روی فایل‌های کد بدون `sim_evidence` رد می‌شوند.

**تصمیم.** تا تحویل VS-2، شواهد `sim_evidence` برای اسلایس Spine از **هارنس sim-world موجود** تأمین می‌شود: تست‌هایی که با `VirtualClock` و `MARZ_WORLD=sim` و seed ثبت‌شده اجرا می‌شوند (`TestSimWorld`، `TestSimWorldGuard`، `TestReceiptsInSim`) — یعنی پارتیشن‌بندی رویداد، نگهبان آلودگی prod، و پایداری زنجیره زیر timestampهای یکسان، همه با `seed=1337`. گزارش خام در `artifacts/sim/T-0001/` و `artifacts/sim/T-0004/` بایگانی می‌شود و سناریوها نام‌گذاری می‌شوند (`sim_world_event_partition`، `sim_world_clock_guard`، `sim_world_receipt_chain`، `workflow_yaml_valid`).

**صداقتِ مرز این تصمیم.** این‌ها سناریوهای کامل §۱۶ (node_outage، chaos، …) **نیستند** و ادعای VS-2 نمی‌شود. این پل فقط ثابت می‌کند spine زیر ساعت مجازی و در جهان sim درست رفتار می‌کند — دقیقاً همان کلاس خطایی که برای کدهای VS-1 مهم است. از VS-2 به بعد، `sim_evidence` فقط با سناریوهای واقعی `sim/scenarios/` معتبر است و این پل در همان ADRِ VS-2 بازنشسته می‌شود.

**رد شد.** *(الف) نوشتن receipt بدون sim_evidence با `strict=False`* — دروازه را همان روز اول شل می‌کرد. *(ب) ساخت سناریوهای جعلی با نام‌های §۱۶* — دروغ؛ بدترین گزینه.

---

## D21 — کشف آثار (artifact discovery) در verify.py از ریشهٔ قابل‌بازنویسی است

**زمینه.** نسخهٔ اول `verify.py --schemas` رسیدها را از مسیر کد (`REPO_ROOT`) می‌خواند، نه از `MARZNESHIN_OPS_ROOT`. تست CLI این را گرفت: ریشهٔ موقت (tmp) نمایندهٔ checkout واقعی است و artifactها باید از همان‌جا خوانده شوند.

**تصمیم.** `verify.py` دو ریشه را صریح تفکیک می‌کند: `CODE_ROOT` (درخت کد — برای lintها) و `paths.repo_root()` (artifactها — برای schema/chain/event checks). lintها عمداً روی درخت کد می‌مانند چون موضوعشان خودِ کد است نه دادهٔ حالت.

**دلیل.** همان قاعده‌ای که `paths.py` را وجود داد: کل درخت باید به tmpdir منتقل‌شدنی باشد، وگرنه VS-2 (sim) و drillهای cold-restore (§۱۱.۲) روی دادهٔ واقعی اشتباهی کار می‌کنند.

---

## D22 — دروازهٔ class-B در pre_push شامل `verify --all` + مجموعهٔ تست است

**زمینه.** §۷.۲ ردهٔ B را «مجموعهٔ تست کامل · contract testها · سناریوهای sim · SAST · policy test · `verify.py --chain`» می‌گوید. contract testهای Adapter و سناریوهای sim هنوز وجود ندارند (VS-2/VS-3).

**تصمیم.** `hooks/pre_push.py` در VS-1 دقیقاً دو گام اجرا می‌کند: `unittest discover` (کامل) و `verify.py --all` (که خودش chain + events + schemas + lints را پوشش می‌دهد)، با بودجهٔ ۹۰ ثانیه و fail روی هر قرمز. با تحویل VS-2/VS-3 گام‌های `scripts/sim.py run --changed-only` و contract testها به همین فایل اضافه می‌شوند — workflow `validate.yml` از الان جای آن را با guard `hashFiles('sim/scenarios')` رزرو کرده.

**رد شد.** *اجرای SAST خارجی در hook* — نیازمند network/binary است و قانون «hook بدون شبکه» (G9) را می‌شکند. SAST در workflow `security` (VS-5) می‌آید.

---

## پیامدهای منفی پذیرفته‌شده (به TRADEOFF-REGISTER رفتند)

| تصمیم | هزینه | مهار |
| --- | --- | --- |
| D19 deny-only events | allowهای hook در event log نیست | بازبینی در VS-3؛ rollup ساعتی در compact اگر لازم شد (T19) |
| D20 پل sim-evidence | شواهد، سناریوی کامل §۱۶ نیست | مرز صریح در این ADR؛ بازنشستگی خودکار با VS-2 |
| D21 دو ریشهٔ مجزا | دو مفهوم به‌جای یکی | نام‌گذاری صریح `CODE_ROOT` در مقابل `repo_root()` |
