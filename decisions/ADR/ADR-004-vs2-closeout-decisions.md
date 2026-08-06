# ADR-004 — بستن اسلایس VS-2: انطباق ساعت، fixture قرارداد vault، و ترتیب sys.path تست

- **وضعیت:** Accepted
- **تاریخ:** 2026-07-30
- **تصمیم‌گیرنده:** momo (جلسهٔ S-2026-07-30-VS2-close، ادامه پس از مهاجرت به سومین workspace) — طبق مجوز BUILD-SPEC §۰
- **ورودی:** BUILD-SPEC v2.0 §۱۶/§۱۷ · ADR-001 (D6) · ADR-002 · ADR-003 (D20) · GAP-REPORT-003 · zip ورودی ۲۰۲۶-۰۷-۳۰
- **دامنه:** `sim/**` · `adapters/**` · `tests/test_sim.py` · `artifacts/sim/VS2-closeout.json`

---

## زمینهٔ جلسه — zip سوم: VS-2 نیمه‌ساخته یافت شد

GAP-REPORT-003 اسلایس VS-1 را بسته و VS-2 را «شروع‌نشده» (N8) اعلام کرده بود، اما zip این جلسه **جدیدتر** بود: `scripts/sim.py`، `sim/{world,actors,chaos,report}.py`، `sim/fakes/` (۹ fake)، ۶ سناریوی §۱۶ و `tests/test_sim.py` (۱۷ تست) وجود داشتند و هارنس ۷۲ ساعته واقعاً کار می‌کرد. طبق دستور Owner **هیچ‌کدام بازسازی نشدند.** وضعیت یافته‌شده در ورود (اندازه‌گیری واقعی، نه حدس):

| بررسی | وضعیت در zip |
| --- | --- |
| هارنس sim (۶ سناریو × ۳ seed) | ✅ سبز — ۱۸/۱۸ PASS (۷۲h در ۰٫۲–۰٫۵ ثانیهٔ دیواری) |
| contract test روی ۹ fake | ۸/۹ سبز · ❌ vault (C3) |
| `verify.py --lint-clock` | ❌ ۵ تخطی در ۳ فایل |
| import تست‌ها | ❌ تداخل نام `sim` (پکیج در برابر runner) |

سه تصمیم زیر این سه شکاف را بستند؛ DoD اسلایس با شواهد اجراشده در GAP-REPORT-004 ثبت است.

---

## D23 — fixture مشترک sandbox برای قرارداد vault (`contract/probe`)

**زمینه.** C3 در `adapters/contract.py` می‌گوید: «هر op با payload خوش‌ساخت `ok=True` برگرداند — مسیر موفقیت». اما payload جدول برای `get_secret` مقدار `contract/nonexistent` بود: نامی که fake آن را **درست** (مطابق رفتار vault واقعی: 404/refuse) رد می‌کند. یعنی C3 برای vault از نظر منطقی ارضاناپذیر بود — مسیر موفقیت نمی‌تواند با secret ناموجود اثبات شود.

**تصمیم.** نامِ fixture مشترک `contract/probe` برای `get_secret`/`rotate` در جدول payload ثبت شد و `VaultFake` آن را pre-seed می‌کند. قرارداد برای adapter واقعی (VS-3): sandbox باید همین نام را پیش از اجرای suite seed کند — این الزام در کامنت `_payload_for` مستند است.

**دلیل.** §۴: fake و adapter واقعی **همان** suite را پاس می‌کنند؛ پس fixture هم باید مشترک و صریح باشد، نه ضمنی. ردِ secret ناموجود همچنان رفتار درست fake است و در C4/C8 پوشش دارد.

**رد شد.** *(الف) auto-provision تنبل در fake* — fake از رفتار واقعی vault منحرف می‌شد (§۴: واگرایی = sim بی‌ارزش). *(ب) حذف C3 برای vault* — شل کردن دروازه.

---

## D24 — RNG فیزیکی جهان، استریم خصوصی با seed است (معافیت مستند `clock-ok`)

**زمینه.** `verify.py --lint-clock` الگوی `random.Random(` را بیرون `lib/clock.py` ممنوع می‌کند (D6) و `sim/world.py:61` را گرفته بود. قاعده از قبل راه فرار دارد: مارکر درون‌خطی `clock-ok` با توجیه (همان قرارداد `paths._resolve_day`).

**تصمیم.** `World` استریم `random.Random(seed)` **خصوصی** خود را نگه می‌دارد و خط با `clock-ok` + کامنت توجیهی علامت خورد. جهان `clock.rng()` را **به اشتراک نمی‌گذارد**: اگر fakeها/بازیگران از همان استریم بکشند، ترتیب مصرف‌کننده‌ها استریم فیزیکی را perturb می‌کند و replay را وابسته به ترتیب اجرا می‌کند — دقیقاً نقیض D6. زمان جهان از VirtualClock تزریق‌شده در runner می‌آید؛ RNG فیزیکی جداست.

**دلیل.** D6 دو چیز می‌خواهد: زمانِ مجازی و بازتولیدپذیری با seed. هر دو بدون اشتراک استریم حاصل می‌شوند؛ لینت با توجیه مستند سبز است، نه با تزویج معماری.

**رد شد.** *تزریق `clock.rng()` به World* — کوپلینگ پنهان بین مصرف‌کننده‌های تصادفی؛ شکستن تفکیک «حقیقت فیزیکی در برابر مشاهدهٔ ایجنت».

---

## D25 — مهلت و backoff در adapters از lib/clock تغذیه می‌شوند (import تنبل)

**زمینه.** دو تخطی دیگر لینت در `adapters/base.py` بود: `deadline_remaining_s` با `datetime.now()` و `backoff_delays` با `random.Random()` پیش‌فرض. زیر VirtualClock مهلت‌ها در زمان مجازی تعریف می‌شوند و `now()` دیواری همه را فوراً منقضی می‌کرد — باگ واقعی، نه فقط لینت.

**تصمیم.** هر دو از `lib.clock` تغذیه می‌کنند: `clock.now()` برای مهلت و `clock.get_clock().rng()` برای jitter پیش‌فرض (در production هم seeded است و seed در receipt ثبت می‌شود). import به‌صورت **تنبل درون‌تابعی** است تا `adapters.base` در جداسازی (مثلاً contract runner آیندهٔ VS-3 روی sandbox) بدون راه‌اندازی sys.path قابل import بماند. `adapters/contract.py::_deadline` هم به `clock.now()` سوئیچ شد.

**رد شد.** *fallback بی‌صدا به ساعت دیواری* — نقض fail-closed: در sim باید بلند بشکند، نه اینکه بی‌صدا زمان اشتباه بدهد.

---

## D26 — در تست‌ها ریشهٔ repo مقدم بر `scripts/` است (تداخل نام `sim`)

**زمینه.** `tests/test_sim.py` ابتدا `REPO` و سپس `REPO/scripts` را در `sys.path` می‌گذاشت (insert(0) دوم جلوتر می‌ایستد) ⇒ `import sim` به‌جای پکیج `sim/`، runner یعنی `scripts/sim.py` resolve می‌شد و `from sim import actors` درونش circular می‌افتاد. فقط اولین تست الفبایی (`test_analytics`) خطا می‌خورد چون import نیمه‌کاره از sys.modules پاک می‌شد و side-effect مسیر runner تست‌های بعدی را نجات می‌داد — رفتار وابسته به ترتیب، یعنی تست flake در انتظار.

**تصمیم.** ترتیب درج معکوس شد: `REPO` مقدم بر `scripts/` + کامنت علت. پکیج `sim/` همیشه برنده است؛ `lib` و اسکریپت‌ها همچنان از مسیر `scripts/` resolve می‌شوند (در ریشهٔ repo همنام ندارند).

**رد شد.** *تغییر نام runner* — شکستن قرارداد CLI مستند `scripts/sim.py` در BUILD-SPEC §۱۶ و CI.

---

## بازنشستگی پل D20 (ADR-003)

طبق وعدهٔ ADR-003: از این جلسه `sim_evidence` فقط با سناریوهای واقعی `sim/scenarios/` ثبت می‌شود. receipt بستن VS-2 (T-0006) شواهدش ۶ سناریو × ۳ seed با گزارش `artifacts/sim/VS2-closeout.json` است. پل D20 بازنشسته شد — تاریخچه‌اش در ADR-003 و artifacts T-0001/T-0004 باقی می‌ماند.

## پیامدها

- lint-clock اکنون ۴ مسیر (`scripts, hooks, sim, adapters`) را سبز می‌بیند و هر معافیت آینده باید همین‌قدر صریح توجیه شود.
- قرارداد adapter (§۴) از همین جلسه روی هر ۹ fake ۱۰۰٪ سبز است — مبنای contract test adapterهای واقعی VS-3.
- هزینه: fixture vault باید در sandbox واقعی (VS-3) تکرار شود؛ در TRADEOFF-REGISTER ثبت شد.
