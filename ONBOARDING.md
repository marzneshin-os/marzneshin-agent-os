# ONBOARDING — ادامهٔ پروژهٔ «Marzneshin Autonomous OS»

> **این فایل را اول از همه بخوان.**
> اگر تو یک اکانت/سشن جدید هستی و هیچ حافظه‌ای از جلسات قبلی نداری، این سند تنها چیزی است
> که برای ادامهٔ درستِ پروژه لازم داری. متن انگلیسی معادل در بخش `## ENGLISH` پایین همین فایل است.

این پروژه چند سشنی است. هر بار که کردیت/توکنِ یک اکانت تمام می‌شود، کل مخزن به صورت zip
به اکانت بعدی منتقل می‌شود. تمام دانشِ پروژه **داخل خودِ مخزن** است، نه در حافظهٔ گفتگو.
پس هرگز حدس نزن — فقط از فایل‌ها بخوان.

---

## قانون طلایی

مخزن (GitHub) تنها منبع حقیقت (SSoT) است. `state/STATE.json` مشتقی از event log است، نه منبع اصلی.
هر چیزی که در فایل‌ها نیست، «وجود ندارد». اگر جایی مشخص نیست، آن را به عنوان سؤالِ Owner ثبت کن.

---

## مرحلهٔ ۱ — خواندن اجباری (به همین ترتیب، بدون جهش)

| # | فایل | چه چیزی به تو می‌دهد |
|---|------|----------------------|
| ۱ | `state/STATE.json` | فاز فعلی، اسلایس فعال (VS-x)، آخرین شمارهٔ رسید، سلامت، متریک‌ها |
| ۲ | `state/HANDOFF.md` | **مهم‌ترین فایل.** بخش «Next session — start here» دقیقاً قدم بعدی را می‌گوید |
| ۳ | `CONTEXT-PACK.md` | خلاصهٔ فشردهٔ وضعیت برای بازیابی سریع context |
| ۴ | `CLAUDE.md` | قوانین پایدار و غیرقابل‌نقض (invariants: I1..In) |
| ۵ | `BUILD-SPEC.md` | سند حاکم. حداقل §0 (پروتکل جلسه)، §16 (سناریوهای الزامی)، §17 (DoD) |
| ۶ | `decisions/ADR/` | بالاترین شمارهٔ ADR = آخرین تصمیم‌های مصوب (Dxx). این‌ها بازِ بحث نیستند |
| ۷ | `decisions/GAP-REPORT-*.md` | آخرین شماره = شکاف‌های باقی‌مانده |
| ۸ | `decisions/TRADEOFF-REGISTER.md` | بدهی فنیِ **عمدی**. قبل از «بهبود» چیزی اینجا را چک کن |
| ۹ | `RECOVERY.md` | مسیر بازیابی در صورت خرابی یا از‌دست‌رفتن دسترسی |

اگر بین `HANDOFF.md` و حافظه/حدسِ تو تناقض بود، **فایل برنده است**.

خواندن `receipts/_chain` و آخرین رسیدهای `receipts/<سال>/` کمک می‌کند بفهمی
«آخرین کارِ واقعاً سبزشده چه بود».

---

## مرحلهٔ ۲ — بازسازی محیط

`.venv` عمداً در zip نیست (مسیرهای مطلقِ ماشین قبلی بی‌اعتبار می‌شوند). دوباره بساز:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml jsonschema
```

همچنین برای فعال‌سازی حافظهٔ دائمی عامل‌ها، باید سرور AgentMemory را در یک ترمینال جداگانه اجرا کنی (حافظه در `state/agentmemory/` ذخیره می‌شود):

```bash
XDG_DATA_HOME=$PWD/state npx -y @agentmemory/agentmemory
```
توجه: هرگز از نصبگر بومی پلاگین AgentMemory در Claude Code استفاده نکن، چون هوک‌های امنیتی سیستم‌عامل را دور می‌زند.

اگر `requirements.txt` وجود داشت، از آن استفاده کن.

---

## مرحلهٔ ۳ — پروتکل شروع جلسه (FSP، الزامی — BUILD-SPEC §0)

```bash
python3 scripts/fsp.py status
python3 scripts/killswitch.py reconcile --skip-auto --by <شناسهٔ-تو>
python3 scripts/fsp.py claim <نام-اسلایس> --agent <شناسهٔ-تو>
```

نکته: heartbeat پس از پایان جلسهٔ قبلی همیشه stale می‌شود (>900s). این خرابی نیست؛
`reconcile` برای همین وجود دارد. اگر lease قبلی باز مانده، اول release/expire کن، بعد claim.

---

## مرحلهٔ ۴ — تأیید baseline پیش از هر تغییر

هرگز کد ننویس تا baseline سبز باشد. **فقط یک دستور** لازم است:

```bash
python3 scripts/health.py            # tests + verify + sim، خروجی ~۴ خط
```

`health.py` سه گیت را اجرا می‌کند، خروجی طولانی‌شان را داخل خودش می‌بلعد و فقط خلاصه چاپ می‌کند
(همین یعنی صرفه‌جویی چند هزار توکن در هر جلسه). با `state/HEALTH-BASELINE.json` هم مقایسه می‌کند،
پس رگرسیون را حتی وقتی همهٔ گیت‌ها «سبز» هستند می‌گیرد.

```bash
python3 scripts/health.py --skip-sim         # حلقهٔ سریع هنگام کد زدن
python3 scripts/health.py --seeds 11         # فقط یک seed (sim کندترین گیت است)
python3 scripts/health.py --verbose          # جزئیات خرابی (محدود به ۸ مورد)
python3 scripts/health.py --json             # برای CI یا ضمیمهٔ رسید
python3 scripts/health.py --save-baseline    # ثبت کفِ سبز جدید (فقط روی run سبز)
```

- کد خروج: `0` سبز، `1` خرابی یا رگرسیون (یا ردِ ذخیرهٔ baseline)، `2` گیت اجرا نشد (fail-closed).
- خط `[REGRESSION]` → عدد از کفِ baseline پایین‌تر آمده. **اول** این را درست کن.
- اگر باید عدد جدید را به رسمیت بشناسی (تست اضافه کردی)، `--save-baseline` بزن.
- `--save-baseline` هرگز کف را باریک نمی‌کند (ADR-009): اگر baseline فعلی گیتی را دنبال کند که در این اجرا اجرا نشده (مثل `coldrestore`)، ذخیره با کد ۱ رد می‌شود و کف دست‌نخورده می‌ماند. گیتِ جاافتاده را اجرا کن تا ذخیره کل کف را پوشش دهد، یا برای بازنشانیِ عمدی فایل baseline را حذف کن.

سه گیت پیش‌فرض **read-only** هستند و `git status` را تمیز می‌گذارند؛ پس قبل از گرفتن lease هم
می‌توانی اجراشان کنی. برای درل §11.2:

```bash
python3 scripts/health.py --coldrestore   # ⚠ prod event می‌نویسد و STATE را بازتولید می‌کند
```

این یکی read-only **نیست** — فقط بعد از claim کردن lease و وقتی HANDOFF خواسته بود اجرا کن.

---

## مرحلهٔ ۵ — پیدا کردن «کار بعدی»

هرگز خودت کار اختراع نکن. اولویت به این ترتیب:

1. رگرسیونِ دیده‌شده در مرحلهٔ ۴
2. بخش «Next session — start here» در `state/HANDOFF.md`
3. اقلام بازِ DoD اسلایس فعال در `BUILD-SPEC.md` §17
4. سناریوهای پیاده‌نشدهٔ §16 (با `scripts/sim.py` مقایسه کن)
5. آخرین `GAP-REPORT`

اگر HANDOFF می‌گوید اسلایس فعلی بسته شده، اسلایس بعدی را از BUILD-SPEC شروع کن — نه هیچ کار دیگری.

---

## مرحلهٔ ۶ — چرخهٔ کار (Sim-first، قانون I11)

هیچ کدی بدون شواهد سبزِ sim به production نمی‌رود.

1. سناریو/سیم مربوطه را **اول** بنویس یا اجرا کن (باید قرمز شود)
2. حداقلِ کدِ لازم را بنویس — increment کوچک، نه بازنویسی بزرگ
3. تست + verify + sim را اجرا کن تا سبز شود
4. رسید بساز و زنجیره را به‌روز کن (رسیدها append-only هستند)
5. `STATE.json` را از event log **بازتولید** کن، نه ویرایش دستی

increment را کوچک نگه دار: هر افزایش باید مستقلاً سبز و قابل‌رسید باشد،
چون ممکن است کردیتِ تو وسط کار تمام شود.

---

## کارهای ممنوع (این‌ها پروژه را خراب می‌کنند)

- ویرایش دستی `state/events/*`، `receipts/_chain`، یا `_anomalies.json`
  → ناهنجاری‌های seq **فقط** با `scripts/anomaly.py` ثبت/بسته می‌شوند
- ویرایش دستی `STATE.json` به‌جای بازتولید از event log
- حذف یا تغییر رسیدهای قبلی (append-only)
- نقض هر invariant در `CLAUDE.md`
- «رفعِ» چیزی که در `TRADEOFF-REGISTER.md` بدهی عمدی ثبت شده
- تصمیم‌گیری به جای Owner در بلاکرها (کلید، هزینه، دسترسی، سیاست)
- fail-open کردن اجزایی که عمداً fail-closed هستند
  (مثال: کلاینت‌های A2A بدون heartbeat تازه باید fail-closed بمانند)
- بردن mock جعلی به production برای دور زدن بلاکر
  (mock فقط در `sim/` و `tests/` مجاز است و باید صریحاً برچسب‌گذاری شود)
- پایان جلسه بدون به‌روزرسانی HANDOFF و release کردن lease

---

## بلاکرهای Owner

مواردی که فقط مالک پروژه می‌تواند حل کند (توکن، هزینه، برنامهٔ کلان، کانال هشدار خارج از باند)
در `HANDOFF.md` با شناسهٔ `Oxx` فهرست شده‌اند. روی این‌ها گیر نکن: شفاف گزارش کن و
کارهای غیروابسته را ادامه بده.

---

## مرحلهٔ ۷ — پروتکل پایان جلسه (اجباری، حتی وقتی کردیت کم است)

وقتی حس کردی توکن دارد تمام می‌شود، **زودتر** از آنچه فکر می‌کنی جلسه را ببند.
یک جلسهٔ کوچکِ بسته‌شده بهتر از یک جلسهٔ نیمه‌کارهٔ گم‌شده است.

1. کار نیمه‌تمام را به نقطهٔ سبز برگردان (یا صریحاً WIP علامت بزن)
2. رسید بساز و زنجیره را ببند
3. `STATE.json` را از event log بازتولید ک��
4. `state/HANDOFF.md` را کامل بازنویسی کن و این‌ها را بنویس:
   - چه کاری تمام شد + شمارهٔ رسید
   - اعداد سبز فعلی (تست / verify / sim)
   - **«Next session — start here»**: دقیقاً قدم بعدی
   - هر ناهنجاری گمراه‌کننده‌ای که دیدی و **رگرسیون نیست**
   - بلاکرهای بازِ Owner
5. `CONTEXT-PACK.md` را با `scripts/context_pack.py` به‌روز کن
6. اگر تصمیم معماری گرفتی → ADR جدید بنویس
7. lease را release کن: `python3 scripts/fsp.py release --agent <شناسه>`
8. کل مخزن را zip کن (بدون `.venv`) و به Owner تحویل بده

---

## اولین چیزی که به Owner می‌گویی

پس از مرحلهٔ ۴ و قبل از نوشتن کد، یک خلاصهٔ ۵ خطی بده:
**فاز و اسلایس فعال / آخرین رسید / اعداد سلامت / کاری که انتخاب کردی / بلاکرهای باز.**
سپس شروع کن.

---

## Token budget — قواعد اجباری مصرف توکن

توکن در این پروژه یک منبعِ محدود مثل زمان است. جلسه‌ای که توکنش وسط کار تمام شود،
نه فقط کارِ خودش را از دست می‌دهد، بلکه اکانت بعدی را مجبور می‌کند همان کار را از صفر کشف کند.
پس این قواعد اختیاری نیستند:

### ۱. تقسیم ۶۰ / ۲۰ / ۲۰

| سهم | مصرف |
|-----|------|
| ۶۰٪ | نوشتن کد و سناریو |
| ۲۰٪ | اجرای گیت‌ها و رفع خرابی |
| ۲۰٪ | **رزرو دست‌نخورده** برای پروتکل پایان جلسه (مرحلهٔ ۷) |

آن ۲۰٪ آخر را زیر هیچ شرایطی خرج کد نکن. اگر خرج شود، جلسه بدون HANDOFF می‌میرد
و این گران‌ترین اتفاقِ ممکن در این پروژه است.

### ۲. خواندن هدفمند، نه خواندن کامل

- ترتیب مرحلهٔ ۱ را رعایت کن؛ `CONTEXT-PACK.md` دقیقاً برای همین ساخته شده.
- از `BUILD-SPEC.md` فقط بخش‌های لازم را بخوان (§0، §16، §17) — نه کل سند.
- برای پیدا کردن کد **grep** بزن، فایل بزرگ را کامل نخوان.
- قبل از هر جستجو از خودت بپرس: «جوابش در CONTEXT-PACK نیست؟»

### ۳. خروجی ابزار را هرگز خام نبلع

بزرگ‌ترین نشتیِ پنهانِ توکن، log کاملِ تست و sim است. راه درست:

```bash
python3 scripts/health.py                 # ✅ ~۴ خط
python3 -m unittest discover -s tests     # ❌ صدها خط
```

اگر مجبور شدی ابزار خامی را اجرا کنی، خروجی را ببُر:
`2>&1 | tail -15` یا `| grep -E "GREEN|RED|FAIL"`.

### ۴. جلسهٔ تازه ارزان‌تر از جلسهٔ طولانی است

در گفتگوی بلند، هر پیام کلِ تاریخچه را دوباره حساب می‌کند؛ هزینه سهمی رشد می‌کند.
وقتی گفتگو سنگین شد: ببند، و جلسهٔ نو را با `ONBOARDING.md` + `CONTEXT-PACK.md` شروع کن.

### ۵. مدل را کم‌حرف کن

اول جلسه به مدل بگو: «توضیح ننویس مگر بپرسم؛ کدِ نوشته‌شده را در چت تکرار نکن؛ فقط diff».
تکرار کد در متنِ پاسخ معمولاً ۳۰–۴۰٪ توکنِ خروجی را بی‌فایده می‌سوزاند.

### ۶. یک increment در هر جلسه

نصفِ سبز و رسیدشده بهتر از دو تای نیمه‌کاره است. increment کوچک = ریسک کمِ از‌دست‌رفتن کار.

### ۷. کارهای مکانیکی را به مدلِ ارزان بده

اجرای گیت‌ها، به‌روزرسانی HANDOFF، ساخت رسید، جستجو → مدل ارزان.
طراحی و کدِ سختِ سناریو → مدل قوی.

---

## ENGLISH — quick version

You are a fresh session with **no memory** of prior work. All project knowledge lives in this repo.

1. **Read in order:** `state/STATE.json` → `state/HANDOFF.md` → `CONTEXT-PACK.md` → `CLAUDE.md`
   → `BUILD-SPEC.md` (§0, §16, §17) → newest `decisions/ADR/` → newest `decisions/GAP-REPORT-*`
   → `decisions/TRADEOFF-REGISTER.md` → `RECOVERY.md`. On conflict, **the files win**.
2. **Rebuild env:** `python3 -m venv .venv && source .venv/bin/activate && pip install pyyaml jsonschema`. 
   Also run the AgentMemory server in a separate terminal to enable persistent agent memory:
   `XDG_DATA_HOME=$PWD/state npx -y @agentmemory/agentmemory`
   Never use the native plugin installer for AgentMemory as it bypasses Marzneshin's security hooks.
3. **Session start (FSP, mandatory):** `fsp.py status` → `killswitch.py reconcile --skip-auto --by <id>`
   (heartbeat is always stale after a handoff — not a failure) → `fsp.py claim <slice> --agent <id>`
4. **Verify baseline green** before touching code with ONE command: `python3 scripts/health.py`.
   It runs tests + verify + sim, swallows their logs, prints ~4 lines, and diffs the counts against
   `state/HEALTH-BASELINE.json`. Exit 0 green / 1 failed-or-regressed / 2 gate could not run.
   A `[REGRESSION]` line means fewer passing items than the floor — fix that first. Use
   `--verbose` for bounded detail, `--skip-sim` for the fast loop, `--save-baseline` to accept a
   new green floor. `--save-baseline` never narrows the floor (ADR-009): if the current baseline
   tracks a gate this run did not execute (e.g. `coldrestore`), the save is refused with exit 1
   and the floor stays untouched — run the missing gate, or delete the baseline file to reset it
   deliberately. The three default gates are read-only; `--coldrestore` is not (it writes prod
   events and regenerates STATE, so run it only while holding the lease).
5. **Pick next work** only from: regression → HANDOFF "Next session" → open DoD items (§17)
   → unimplemented §16 scenarios → newest GAP-REPORT. Never invent work.
6. **Sim-first (I11):** failing sim → minimal code → green tests/verify/sim → receipt → regenerate STATE.
   Keep increments small; your credits may run out mid-task.
7. **Never:** hand-edit events/receipts/`_anomalies.json`/STATE, delete receipts, violate a `CLAUDE.md`
   invariant, "fix" an accepted tradeoff, decide an Owner blocker, make fail-closed components fail-open,
   or ship mocks to production.
8. **Session end (mandatory):** reach green → receipt → regenerate STATE → **rewrite `state/HANDOFF.md`**
   (done + receipt id, green numbers, exact next step, misleading non-regressions, open `Oxx` blockers)
   → refresh `CONTEXT-PACK.md` → new ADR if you made a decision → `fsp.py release` → zip repo without `.venv`.
9. **Token budget (mandatory):** 60% code / 20% gates / 20% *reserved* for step 8 — never spend the
   reserve. Read targeted (CONTEXT-PACK, grep) not whole files. Never swallow a raw test log: use
   `health.py`, or `| tail -15`. Prefer a fresh session over a long one (history is re-billed every
   turn). Tell the model up front: no prose unless asked, no re-printing code, diffs only. One
   increment per session. Mechanical work (gates, HANDOFF, receipts) does not need the expensive model.
