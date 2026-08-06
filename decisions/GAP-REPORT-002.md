# GAP-REPORT-002 — SYNC + GAP SCAN پس از مهاجرت workspace

> **مرجع:** BUILD-SPEC v2.0 · ADR-001 · GAP-REPORT-001
> **نویسنده:** Owner فنی (Claude Opus 5) · **تاریخ:** 2026-07-28
> **مبنای قرارداد:** BUILD-SPEC §۰ پروتکل جلسه، گام‌های ۱ (SYNC) و ۲ (GAP SCAN)
> **علت جلسه:** workspace از اکانت قبلی import شد؛ کار قبلی با خطای `402 Virtual key budget exceeded` قطع شده بود، نه با خطای فنی.
> **وضعیت:** VS-1 نیمه‌کاره. یک لایه کامل و اثبات‌شده، بقیهٔ اسلایس دست‌نخورده.

---

## ۰) خلاصهٔ اجرایی (اگر فقط یک بند می‌خوانی، این را بخوان)

سه واقعیت:

1. **کار قبلی واقعی بود، نه اسکلت.** ۲۷۰۰ خط پایتون در `scripts/lib/` وجود دارد که **کامپایل می‌شود، اجرا می‌شود، و invariantهایی که ادعا می‌کند را واقعاً اجبار می‌کند.** این را با ۱۳ تست دود end-to-end اثبات کردم (§۳). هیچ `TODO`، هیچ `mock`، هیچ تابع خالی در آن نیست.
2. **فقط ۱ مورد از ۸ خروجی مورد انتظار §۲۰ تحویل شده است.** `scripts/lib/` تمام است (بند ۶، منهای تست). بندهای ۱–۵ و ۷–۸ صفر پیشرفت دارند: هیچ hook، هیچ workflow، هیچ schema، هیچ `sim/`، هیچ `CLAUDE.md`/`STATE.json`/`HANDOFF.md`، هیچ receipt نمونهٔ واقعی.
3. **کل پروژه تا لحظهٔ این گزارش داخل یک فایل `.rar` حبس بود.** هیچ فایلی در workspace به‌صورت قابل‌کار وجود نداشت. در این جلسه استخراج و در `General/marzneshin-ops/` مستقر شد.

**تخمین پیشرفت VS-1:** حدود **۳۵٪**. لایهٔ سخت‌ترش (کتابخانهٔ مشترک) تمام است؛ لایهٔ نازک روی آن (hookها، workflowها، CLI scripts) و اسناد وضعیت نیستند.

**یک هشدار صریح:** `scripts/lib/` به فایل‌هایی ارجاع می‌دهد که **وجود ندارند** — `scripts/verify.py --chain`، `--lint-imports`، `--lint-clock`، `--repair-head`، `scripts/compact.py --rebuild`، `scripts/fsp.py bootstrap`. این‌ها در docstringها به‌عنوان مکانیزم اجبار وعده داده شده‌اند. تا ساخته نشوند، **هیچ‌کدام از آن اجبارها در CI فعال نیست.** خودِ کتابخانه صادق است؛ زنجیرهٔ اجبار پیرامونش نیست.

---

## ۱) وضعیت اعتبار AI — این را نمی‌توانم خودم تأیید کنم

تو صریح خواستی قبل از شروع، کافی‌بودن اعتبار را تأیید کنم. **نمی‌توانم، و طبق قرارداد خودِ سند نباید تظاهر کنم که می‌توانم.**

| مورد | وضعیت |
|---|---|
| خواندن موجودی/سقف اکانت از داخل این محیط | **ناممکن.** هیچ ابزاری در دسترس من موجودی یا سقف virtual key را برنمی‌گرداند. |
| شواهد تجربی این جلسه | این جلسه ~۴۰ فراخوان ابزار و چند نوبت مدل رده‌بالا (شامل خواندن ۱۱۱۰ خط BUILD-SPEC) را **بدون 402** کامل کرد. |
| نتیجهٔ درست از این شواهد | اعتبار **صفر نیست**. دربارهٔ اینکه برای اتمام VS-1 تا VS-2 **کافی** است، هیچ چیز ثابت نمی‌کند. |

**قانون حاکم — BUILD-SPEC §۰:** «ادامه دادن وقتی وضعیت یک کنترل ایمنی (kill switch، lease، **budget**، probe) قابل خواندن نیست [ممنوع است]. "نمی‌دانم" هم‌ارز "متوقف شو" است.»

بودجه صریحاً در آن فهرست است. پس **گزارش‌نویسی و SYNC را انجام دادم (هزینهٔ ناچیز)، اما ساخت سنگین را شروع نکردم.** این نه محافظه‌کاری است و نه تعارف؛ اجرای همان قاعده‌ای است که قبلاً همین پروژه را به کشتن داد.

**آنچه از تو لازم است (یکی از این دو):**
- موجودی را در Settings → Billing نگاه کن و عدد را بگو؛ یا
- بگو «برو» و بپذیر که ممکن است وسط یک اسلایس قطع شود.

**اگر «برو» بگویی، این‌ها را برای مهار قطعی‌شدن اعمال می‌کنم:** کار به قطعه‌های کوچک و مستقل شکسته می‌شود، هر قطعه بلافاصله روی دیسک نوشته می‌شود (نه انبار شدن در context)، و بعد از هر قطعه `HANDOFF.md` بازنویسی می‌شود — تا قطع شدن در هر نقطه، حداکثر یک قطعه کار را از دست بدهد. این دقیقاً همان چیزی است که در قطع قبلی وجود نداشت.

---

## ۲) محیط سنجیده‌شده (بازاندازه‌گیری، نه کپی از GAP-REPORT-001)

| بررسی | نتیجه | تغییر نسبت به GAP-REPORT-001 |
|---|---|---|
| Python | 3.11.2 ✔ | بی‌تغییر |
| Node | v24.18.0 ✔ | بی‌تغییر |
| Secrets ذخیره‌شده | **۰** | بی‌تغییر — همهٔ Adapterها بی‌credential |
| `gh` CLI | نصب، `GH_TOKEN` **نامعتبر** | بی‌تغییر — A1 هنوز مسدودکننده |
| `jsonschema` (پایتون) | **نصب نیست** | **جدید.** `validate.py` در strict mode عمداً fail می‌کند تا وانمود نکند اعتبارسنجی کامل است. برای CI باید نصب شود. |
| git در workspace | یک commit مصنوعی (`mfs sync`)، commit/push بلاک | بی‌تغییر — Moxt نمی‌تواند SSoT باشد |
| ابزار استخراج RAR | نبود؛ در این جلسه `unar` نصب شد | **جدید** |
| unrar/p7zip از پیش | موجود نبود | **جدید** — اگر sandbox بازنشانی شود، `sudo apt-get install unar` لازم است |

هیچ‌کدام از این‌ها مانع VS-1/VS-2 نیستند (هر دو صفر credential لازم دارند).

---

## ۳) موجودی فایل‌به‌فایل — با تأیید اجرا، نه فقط وجود

هر فایل باز و خوانده شد. برای کد، فقط به خواندن بسنده نکردم: یک تست دود ۱۳بخشی نوشتم که هر ماژول را واقعاً اجرا می‌کند.

### ۳.۱) اسناد

| فایل | خط | محتوا | وضعیت |
|---|---|---|---|
| `BUILD-SPEC.md` | **1110** | BUILD-SPEC **v2.0** کامل: ۲۰ بخش، ۱۸ invariant، ۵ قانون آهنین + قانون ششم، ۱۲ اسلایس با DoD، ۱۹ ایجنت در ۳ Tier، schemaهای canonical (STATE/Event/Receipt/Agent Card/A2A Envelope/Lease)، transport سه‌لایه، policy engine، kill switch پنج‌مسیره، simulation harness، trade-off register | ✅ **کامل و حاکم.** سند مرجع اجرا. |
| `decisions/GAP-REPORT-001.md` | **364** | تحلیل v1.0: ۱۹ GAP (۶ blocker، ۹ major، ۴ minor)، هر یک با اصلاح. اندازه‌گیری واقعی محیط. ۵ وابستگی مسدودکننده A1–A5 | ✅ **کامل.** بسته‌شده — همهٔ GAPها در v2.0 جذب شدند. |
| `decisions/ADR/ADR-001-foundational-architecture.md` | **115** | ۱۰ تصمیم D1–D10 با زمینه/تصمیم/دلیل/پیامد + جدول هزینه‌های پذیرفته‌شده | ✅ **کامل.** وضعیت Accepted. |
| `decisions/archive/BUILD-SPEC-v1.0-RETIRED.md` | 531 | نسخهٔ ۱.۰ | ⚪ **بازنشسته** طبق v2.0 §۰. مرجع تاریخی؛ به آن استناد نکن. |
| `AGENTS.md` (در archive) | **0** | خالی | ⚠️ **صفر بایت.** کپی نشد. |

### ۳.۲) کد — `scripts/lib/` (۲۷۰۰ خط، ۱۴ فایل)

| فایل | خط | چه پیاده کرده | placeholder/mock/pass؟ |
|---|---|---|---|
| `__init__.py` | 31 | قرارداد ترتیب import (گراف بدون سیکل)، `__version__ = 1.1.0` | ❌ پاک |
| `paths.py` | 175 | resolve ریشهٔ repo با override محیطی `MARZNESHIN_OPS_ROOT` (کلید جابه‌جایی کل درخت به tmpdir برای sim)، ۲۵ helper مسیر canonical، slug امن فایل‌سیستم | ❌ پاک |
| `clock.py` | 142 | `Clock` Protocol + `RealClock` + `VirtualClock`. ساعت مجازی ۷۲ ساعت را لحظه‌ای جلو می‌برد؛ `sleep()` فوری است. RNG با seed در **هر دو** حالت | ❌ پاک (`...` = بدنهٔ Protocol، درست) |
| `ids.py` | 117 | ULID مونوتونیک (Crockford base32، ۴۸بیت زمان + ۸۰بیت تصادف؛ در یک میلی‌ثانیه بخش تصادفی **افزایش** می‌یابد نه قرعه‌کشی مجدد — برای ساعت مجازی حیاتی)، `canonical_json` قطعی، خانوادهٔ sha256، `idempotency_key` | ❌ پاک |
| `atomic.py` | 136 | نوشتن اتمی (tmp + fsync + `os.replace` + fsync دایرکتوری)، append با `O_APPEND`، `CorruptState` به‌جای بازگشت بی‌صدا به default | ❌ پاک (`pass` = بدنهٔ `except OSError` عمدی) |
| `redact.py` | 197 | ۱۶ الگوی provider (GitHub/AWS/Slack/Telegram/OpenAI/Anthropic/Stripe/ClickUp/private key/JDBC…)، آنتروپی شانون برای الگوهای عمومی، allowlist ضد false-positive، پیمایش عمیق ساختار با گزارش مسیر کلید | ❌ پاک |
| `leases.py` | 276 | lease با **fencing token** واقعی: شمارندهٔ مونوتونیک repo-wide، `assert_writable` که token عقب‌تر را رد می‌کند، `revoke` که token را می‌سوزاند (STEP 1 پروتکل جانشینی)، `find_zombies` | ❌ پاک |
| `killswitch.py` | 337 | K1 (فایل) + K2 (متغیر محیطی) با **fail-closed واقعی**: پنجرهٔ تازگی ۱۵ دقیقه، فایل KILL خراب = kill سراسری، scope ناشناس = kill سراسری، sidecar heartbeat که «چیزی خراب نیست» را از «کسی سه روز چک نکرده» تفکیک می‌کند | ❌ پاک |
| `receipts.py` | 399 | ۵ وضعیت، اجبار DoD به‌ازای وضعیت (`complete` بدون rollback تست‌شده رد می‌شود)، زنجیرهٔ هش با `prev_receipt_hash`، `write_tombstone` برای reaper، `verify_chain` که دستکاری و حذف را تشخیص می‌دهد، `stats()` با crash_rate | ❌ پاک |
| `state.py` | 193 | STATE.json به‌عنوان artifact **مشتق**، نوشتن fenced، تشخیص کهنگی ۲۴ساعته، fail-closed روی snapshot خراب، `summarize()` انسانی‌خوان | ❌ پاک |
| `budget.py` | 282 | دفتر سلسله‌مراتبی چهارسطحی (workspace→tier→agent→task)، **رزرو قبل / تسویه بعد** با رزروهای معلق که علیه سقف حساب می‌شوند، جدول قیمت مدل، مسیریابی مدل بر اساس نوع کار، `forecast` خطی، `spike_detected` با **میانه** (نه میانگین) | ❌ پاک (`pass` = بدنهٔ کلاس استثنا) |
| `policy.py` | 315 | ماتریس ریسک ۲۰ردیفه با **default-deny** برای capability ناشناس، ارث‌بری taint (کمترین اعتماد برنده)، سقف L1 اجباری روی ورودی untrusted، تفکیک وظایف (self-review = deny)، سه کلاس idempotency با **رد تضعیف** forever→none، `wrap_untrusted` با escape مرزها | ❌ پاک |
| `events.py` | 254 | append-only پارتیشن‌شده per-actor، واژگان بستهٔ ۴۵ نوع رویداد، `actor_seq` با اسکن برگشتی ۷روزه برای بقا در rollover تاریخ، **redaction قبل از persist**، `detect_gaps` برای رویداد گم‌شده | ❌ پاک (`pass` = بدنهٔ کلاس استثنا) |
| `validate.py` | 262 | دو حالت: strict (jsonschema، **بدون fallback** — عمدی) و fast (فقط stdlib، برای بودجهٔ ۳ثانیه‌ای hook) با پشتیبانی `$ref`/`oneOf`/`allOf`/enum/pattern/min-max؛ رجیستری upcaster با اعمال زنجیره‌ای و رد مسیر ناموجود | ❌ پاک |

**نتیجهٔ بررسی placeholder:** هر ۱۷ مورد مشکوکی که grep پیدا کرد بررسی شد. **هیچ‌کدام placeholder نیستند** — همه یا بدنهٔ کلاس استثنا (`class LeaseError(Exception): pass`)، یا بدنهٔ متد Protocol (`def now(self) -> datetime: ...`)، یا `except OSError: pass` عمدی، یا رشتهٔ داخل allowlist خودِ اسکنر امنیتی هستند. **این کد ادعای «بدون mock» را رعایت کرده است.**

### ۳.۳) اثبات اجراپذیری — ۱۳/۱۳ سبز

طبق §۰ («ادعای تست پاس شد بدون خروجی واقعی ممنوع»)، خروجی واقعی:

```
[PASS] paths.repo_root resolves via env override      /tmp/smoke/marzneshin-ops
[PASS] clock.VirtualClock 72h advance                 2026-01-01 -> 2026-01-04, لحظه‌ای
[PASS] ids.new_ulid monotonic/sortable/unique         500 ULID، مرتب، بدون تکرار، len=26
[PASS] atomic write/read + CorruptState fail-closed   roundtrip ok، خراب => استثنا
[PASS] redact scan/redact accuracy                    ghp_ شناسایی، ${VAR} false-positive نداد
[PASS] leases fencing token / split-brain guard       token 1->3، عقب‌تر رد، جاری پذیرفته
[PASS] killswitch 5-path fail-closed lifecycle        clone تازه=UNKNOWN (L2 را می‌بندد،
                                                      L4 را باز می‌گذارد) -> RUNNING
                                                      -> KILLED -> RUNNING
[PASS] budget reserve/settle/cap/forecast             رزرو 25k، تسویه 22k، بیش‌ازسقف رد
[PASS] policy risk matrix / taint / SoD / idempotency untrusted -> L1، ناشناس=deny،
                                                      self-review=deny، pricing=deny
[PASS] events emit/partition/redact/gap-detect        seq 1->2، gaps=[]، secret redact شد
[PASS] receipts DoD/chain/tombstone/tamper-detect     DoD اجبار شد، زنجیره معتبر،
                                                      دستکاری تشخیص داده شد
[PASS] state bootstrap/fenced-write/summarize         نوشتن fenced ok، token کهنه رد
[PASS] validate fast-mode + upcaster chain            ۲ خطا روی شیء نامعتبر، upcast ok

TOTAL: 13 passed, 0 failed, 0 soft-failures out of 13
```

نکتهٔ مهم دربارهٔ سه مورد: kill switch روی یک clone تازه واقعاً `UNKNOWN` برمی‌گرداند و واقعاً L2 را می‌بندد در حالی که L4 را باز می‌گذارد — یعنی **fail-closed یک ادعا نیست، رفتار اجراشده است.** دستکاری receipt واقعاً تشخیص داده شد. token کهنه واقعاً رد شد. این سه، هستهٔ ایمنی سیستم‌اند.

⚠️ **این تست دود، تست پروژه نیست.** آن را من در `/tmp` نوشتم تا وضعیت را برایت تأیید کنم. `tests/` در repo **وجود ندارد** (§۴.۲ مورد N4). اولین کار پس از تأیید، تبدیل همین تست به مجموعهٔ رسمی است.

---

## ۴) دو فهرست قطعی

### ۴.۱) ✅ تمام‌شده — **دوباره نساز، توکن خرج نکن**

| # | مورد | شاهد |
|---|---|---|
| D1 | BUILD-SPEC v2.0 (۱۱۱۰ خط) | خوانده شد، حاکم است |
| D2 | GAP-REPORT-001 (۱۹ GAP، همه بسته) | خوانده شد |
| D3 | ADR-001 (D1–D10، Accepted) | خوانده شد |
| D4 | `scripts/lib/paths.py` | اجرا شد |
| D5 | `scripts/lib/clock.py` (ساعت مجازی ۷۲ساعته) | اجرا شد |
| D6 | `scripts/lib/ids.py` (ULID مونوتونیک) | اجرا شد |
| D7 | `scripts/lib/atomic.py` | اجرا شد |
| D8 | `scripts/lib/redact.py` | اجرا شد |
| D9 | `scripts/lib/leases.py` (fencing واقعی) | اجرا شد |
| D10 | `scripts/lib/killswitch.py` (fail-closed واقعی) | اجرا شد |
| D11 | `scripts/lib/receipts.py` (۵ وضعیت + زنجیره) | اجرا شد |
| D12 | `scripts/lib/state.py` | اجرا شد |
| D13 | `scripts/lib/budget.py` (رزرو/تسویه) | اجرا شد |
| D14 | `scripts/lib/policy.py` (taint + سه کلاس idempotency) | اجرا شد |
| D15 | `scripts/lib/events.py` (پارتیشن per-actor) | اجرا شد |
| D16 | `scripts/lib/validate.py` (دو حالت + upcaster) | اجرا شد |

معادل §۲۰ بند ۶ («`scripts/lib/` پایه») — **منهای «با تست»**.

### ۴.۲) ❌ شروع‌نشده — **کار از اینجا ادامه پیدا می‌کند**

**مسدودکنندهٔ بستن VS-1:**

| # | مورد | چرا لازم است |
|---|---|---|
| N1 | `analytics/schemas/*.schema.json` — Event, Receipt, STATE, Agent Card, A2A Envelope, Lease | §۳ می‌گوید همه Draft 2020-12 باشند. `validate.py` آماده است اما **هیچ schemaیی برای خواندن ندارد**. |
| N2 | `hooks/` هفت‌گانه: `session_start`, `pre_tool`, `post_tool`, `pre_commit`, `pre_push`, `task_complete`, `stop` | §۲۰ بند ۳. بدون `task_complete.py` قانون I3 (هر تسک یک receipt) هیچ اجباری ندارد. |
| N3 | `scripts/`: `verify.py` (`--chain`, `--lint-imports`, `--lint-clock`, `--repair-head`), `compact.py`, `fsp.py`, `context_pack.py`, `killswitch.py`, `reaper.py`, `sim.py`, `succession.py`, `experiment_guard.py`, `autonomy_review.py` | **کتابخانه به این‌ها ارجاع می‌دهد و وجود ندارند** (§۰ هشدار). `killswitch.py` = مسیر K4. `reaper.py` = تولیدکنندهٔ tombstone. |
| N4 | `tests/` + پوشش ≥۸۰٪ روی `scripts/lib` | §۱۶.۱. تست دود من در `/tmp` است، نه در repo. |
| N5 | `.github/workflows/`: `validate`, `compact`, `mirror`, `heartbeat` (۴ مورد اول از ۱۱) | §۲۰ بند ۴. `heartbeat` همان چیزی است که K2/K3/K5 را به K1 می‌ریزد — **بدون آن فقط ۲ مسیر از ۵ مسیر kill switch زنده است**. |
| N6 | `CLAUDE.md` (<۴۰۰ خط), `CONTEXT-PACK.md`, `state/STATE.json`, `state/HANDOFF.md`, `RECOVERY.md`, `CODEOWNERS`, `decisions/TRADEOFF-REGISTER.md` | §۲۰ بند ۱–۲. `TRADEOFF-REGISTER.md` اجبار I8 است. |
| N7 | یک receipt نمونهٔ واقعی end-to-end با زنجیرهٔ معتبر | §۲۰ بند ۵ — **مدرک DoD خودِ VS-1** |

**VS-2 و بعد (هیچ‌کدام شروع نشده):**

| # | مورد |
|---|---|
| N8 | `sim/` کامل: `clock.py`, `world.py`, `chaos.py`, `report.py`, `fakes/` (۹ adapter), `scenarios/*.yaml` (۱۴ سناریو) — **کل VS-2** |
| N9 | `adapters/` (۹ adapter × interface §۴ + contract test + fake متناظر) |
| N10 | `agents/{cards,policies,prompts}/` — ۷ Agent Card Tier 0 |
| N11 | `skills/` — ۱۱ SKILL.md با هدر اجباری §۷.۳ |
| N12 | `mcp/`, `plugins/marzneshin-ops/` (۱۲ command با schema خروجی) |
| N13 | `growth/`, `analytics/{events,models,dashboards}/`, `security/{iam,policies,compliance}/`, `configs/`, `infra/` |
| N14 | ۷ workflow باقی‌ماندهٔ CI |
| N15 | `gateway/` — **عمداً ممنوع تا VS-12** (§۱.۲). نساز. |

**سطح workspace (خارج از repo):**

| # | مورد | وضعیت |
|---|---|---|
| N16 | `General/AGENTS.md` | **صفر بایت** |
| N17 | `General/System/Skills/` | فقط `.gitkeep` |
| N18 | Moxt Workflow «Control Room» | ساخته نشده (VS-6، طبق ترتیب صحیح **بعد** از ایجنت‌ها) |
| N19 | AI Teammates | **۰ عدد** — T2 transport به این‌ها وابسته است (VS-3) |

---

## ۵) ⚠️ موارد نصفه‌کاره یا مشکوک — نه فرض، بلکه صریح

اینجا جایی است که خواستی حدس نزنم. ۱۰ مورد یافتم. **هیچ‌کدام کد موجود را بی‌ارزش نمی‌کند؛ اما S1، S2 و S3 قبل از نوشتن اولین schema باید حل شوند، چون اگر بعداً حل شوند مهاجرت داده لازم می‌شود.**

| # | مورد | تحلیل | تصمیم پیشنهادی |
|---|---|---|---|
| **S1** | **تناقض `schema_version`** | کد در `events.py`/`receipts.py`/`state.py` می‌گوید `1.1.0`. BUILD-SPEC §۳ می‌گوید «`schema_version` سراسری این نسخه: **`2.0.0`**». | **سند حاکم است (§۰).** کد به `2.0.0` می‌رود. **باید قبل از نوشتن اولین رویداد واقعی انجام شود** — بعد از آن، upcaster لازم می‌شود. |
| **S2** | **Receipt فیلدهای اجباری §۳.۳ را ندارد** | غایب: `sim_evidence` (**اجبار I11 — بدون آن «هیچ کد بدون sim به prod نمی‌رود» غیرقابل‌اجبار است**)، `idempotency`, `input_provenance`, `agent_lineage`, `autonomy_shadow`, `chain_index`, `transport`, `workstream`↔`why_one_sentence` (به‌نام `reason`), `receipt_hash` (به‌نام `content_hash`), `rollback.tested_in`/`max_ttr_s`, `cost.model_usage`/`budget_reservation_id`. `verification` هم `verifier`/`independent_of_author` و فیلدهای آماری canary (`n`, `n_min`, `p_value`, `conclusive`, `probe_fleet`) را ندارد. | `Receipt` تا انطباق کامل با §۳.۳ گسترش یابد. **قبل از schema و قبل از اولین receipt واقعی.** |
| **S3** | **Event فیلدهای اجباری §۳.۲ را ندارد** | غایب: `world` (**بحرانی** — §۳.۲ می‌گوید رویداد sim هرگز نباید در پارتیشن production بنویسد، و `paths.py` هیچ پارتیشن `state/events/sim/` ندارد)، `transport`, `tick_level`, `trust`, `seed`, `redaction_map`; `actor` هم `lineage`/`model` ندارد. | همان: گسترش + افزودن پارتیشن sim به `paths.py`. **پیش‌نیاز VS-2.** |
| **S4** | `taint.py` و `transport.py` در `scripts/lib/` نیستند | §۲.۲ هر دو را الزام می‌کند. §۱۵.۲ صریح می‌گوید اجبار taint «در `hooks/pre_tool.py` **و در `scripts/lib/taint.py`**». منطق taint **وجود دارد** اما داخل `policy.py` است. `transport.py` کاملاً غایب. | ادغام taint در policy از نظر مهندسی دفاع‌پذیر است → **ADR-002 لازم است** (§۰: انحراف از سند بدون ADR ممنوع). `transport.py` باید ساخته شود (VS-3). |
| **S5** | ترتیب زنجیرهٔ receipt از `completed_at` استنتاج می‌شود | `verify_chain` با `sort(key=(completed_at, task_id))` مرتب می‌کند. زیر **ساعت مجازی** (که در sim هزاران رویداد را در یک timestamp می‌گذارد) این می‌تواند ترتیب را اشتباه بچیند و **شکست کاذب زنجیره** بسازد. §۳.۳ فیلد `chain_index` را دقیقاً برای همین تعریف کرده و کد آن را ندارد. | `chain_index` اضافه شود و ترتیب از آن بیاید، نه از زمان. با S2 یکجا. |
| **S6** | فقط ۲ مسیر از ۵ مسیر kill switch زنده است | K1 و K2 پیاده‌اند. K3 (Moxt)/K4 (CLI)/K5 (خودکار) طراحی درستی دارند (از طریق heartbeat به K1 می‌ریزند) اما `scripts/killswitch.py` و workflow `heartbeat` **وجود ندارند**. یعنی امروز پنجرهٔ تازگی هرگز تازه نمی‌شود مگر دستی. | صادقانه ثبت شود؛ با N3+N5 بسته می‌شود. ادعای «۵ مسیره» تا آن زمان **نکن**. |
| **S7** | `budget.MODEL_PRICING` با سند و واقعیت نمی‌خواند | جدول `claude-opus-4-8`/`sonnet-5`/`haiku-4-5` دارد. BUILD-SPEC همه‌جا `claude-opus-5` می‌گوید و `cheap-tier`. مدل `claude-fable-5` هم وجود دارد و در جدول نیست. اعداد قیمت هم تأییدنشده‌اند. | جدول با شناسه‌های واقعی و قیمت تأییدشده به‌روز شود + ADR (خودِ فایل می‌گوید «هرگز بی‌صدا، همیشه با ADR»). **مستقیماً روی درستیِ محاسبهٔ بودجه اثر دارد.** |
| **S8** | `budget_ledger_file()` → `ledger.ndjson`، سند می‌گوید `ledger.json` | NDJSON برای دفتر append-only **بهتر** است و با انتظام event log هم‌خوان. اما انحراف از §۲.۲ است. | انحراف را نگه دار، در **ADR-002** ثبت کن. |
| **S9** | `_next_actor_seq` فقط ۷ روز به عقب اسکن می‌کند | ایجنتی که >۷ روز بی‌کار باشد، شمارنده‌اش از ۱ شروع می‌شود → `detect_gaps` تکرار/شکاف کاذب گزارش می‌کند. برای ایجنت‌های کم‌کار (Recon شبانه، drill ماهانه) واقعی است. | شمارنده per-actor پایدار در `state/` نگه‌داری شود، نه استنتاج از فایل‌های اخیر. |
| **S10** | MASTER-PLAN v4.0 FINAL در archive نیست | BUILD-SPEC §۰ آن را «ورودی مرجع» می‌نامد و §۲.۲ آن را در ریشهٔ repo می‌خواهد. §۱۰.۵ می‌گوید دانش هر ایجنت = `owns` + **MASTER-PLAN** + BUILD-SPEC. | **ورودی گم‌شده.** اگر داری، بده. اگر نه: BUILD-SPEC v2.0 خودبسنده است (§۰: «هر چیزی که برای ساخت سیستم لازم است، اینجا هست») → ارجاع‌های MASTER-PLAN به‌عنوان اختیاری علامت‌گذاری و در ADR-002 ثبت شود. |

---

## ۶) نقطهٔ دقیق ادامهٔ کار

VS-1 است، نه VS-2. ترتیب پیشنهادی (هر گام یک artifact روی دیسک، تا قطع شدن حداکثر یک گام هزینه داشته باشد):

```
گام ۰  ADR-002  تثبیت S1–S10: نسخهٔ schema، ادغام taint، ledger.ndjson،
                 جدول قیمت مدل، وضعیت MASTER-PLAN         [ارزان، اول انجام شود]
گام ۱  گسترش receipts.py + events.py طبق §۳.۳/§۳.۲ (S2/S3/S5)
                 + پارتیشن sim در paths.py                 [قبل از هر داده واقعی]
گام ۲  analytics/schemas/ — ۶ JSON Schema (N1)             + نصب jsonschema
گام ۳  tests/ — تبدیل تست دود ۱۳بخشی به مجموعهٔ رسمی (N4)
گام ۴  scripts/ — verify.py، fsp.py، compact.py، killswitch.py، reaper.py (N3)
گام ۵  hooks/ — هفت hook رده A + pre_push (N2)
گام ۶  CLAUDE.md، CONTEXT-PACK.md، STATE.json، HANDOFF.md،
                 RECOVERY.md، CODEOWNERS، TRADEOFF-REGISTER.md (N6)
گام ۷  .github/workflows/ — validate، compact، mirror، heartbeat (N5)
گام ۸  یک تسک ساختگی end-to-end: CLAIM → … → HANDOFF با receipt
                 `complete` و زنجیرهٔ سبز (N7)              ← DoD خودِ VS-1
─────── VS-1 بسته می‌شود ───────
سپس VS-2 (sim/) — و تا آن لحظه هیچ کدی به مسیر production نمی‌رود (I11)
```

توجه: گام‌های ۰ و ۱ **باید** قبل از ۲ باشند. اگر schema روی مدل داده‌ای نوشته شود که بعداً تغییر می‌کند، upcaster لازم می‌آید — یعنی هزینهٔ اضافی برای هیچ.

---

## ۷) وضعیت

```plain
SLICE: VS-1 (~35% — scripts/lib کامل و اثبات‌شده؛ hooks/schemas/scripts/workflows/اسناد صفر)
STATUS: amber
DONE:  SYNC کامل · ۲۰ فایل archive باز و خوانده شد (۵۲۳۶ خط) · ۱۳/۱۳ تست دود سبز
       روی کل scripts/lib · repo از .rar به General/marzneshin-ops/ منتقل شد
       · v1.0 به decisions/archive/ بازنشسته شد · ۱۹ مورد شروع‌نشده و ۱۰ مورد
       مشکوک فهرست شد
NEXT:  ADR-002 (تثبیت S1–S10) → گسترش receipt/event طبق §۳.۳/§۳.۲ → JSON Schemas
BLOCKERS:
  B1 (سخت)  اعتبار AI قابل خواندن نیست. §۰ می‌گوید بودجهٔ ناخوانا = توقف.
            تأیید انسانی لازم است.
  B2 (نرم)  GH_TOKEN نامعتبر · ۰ secret → A1 از GAP-REPORT-001 هنوز باز.
            VS-1/VS-2 را مسدود نمی‌کند.
  B3 (نرم)  jsonschema نصب نیست → strict validation در CI کار نمی‌کند (عمدی).
  B4 (نرم)  MASTER-PLAN v4.0 غایب (S10).
RECEIPTS: هیچ. receipts/ خالی است. اولین receipt واقعی خروجی گام ۸ است.
          این گزارش خودش یک receipt نیست — چون هنوز مکانیزم receipt (N3/N2) ساخته نشده.
TOKENS: این جلسه صرف SYNC/GAP SCAN شد، نه ساخت. ساخت هنوز شروع نشده.
```

---

## ۸) دو تصمیمی که خودم گرفتم (طبق مجوز §۰)

1. **استخراج archive به `General/marzneshin-ops/`.** بدون این، «ادامهٔ کار» بی‌معنا بود — هیچ فایل قابل‌ویرایشی وجود نداشت. افزایشی و بازگشت‌پذیر؛ هیچ چیزی بازنویسی نشد. `unar` نصب شد چون هیچ استخراج‌کنندهٔ RAR در محیط نبود.
2. **بازنشستگی v1.0 به `decisions/archive/BUILD-SPEC-v1.0-RETIRED.md`.** v2.0 §۰ می‌گوید «v1.0 بازنشسته می‌شود». نگه‌داشتن دو BUILD-SPEC در ریشه، تضمین می‌کرد که یک جلسهٔ آیندهٔ اشتباهی سند غلط را بخواند.

**آنچه عمداً نکردم:** هیچ کد جدیدی ننوشتم. علتش B1 است — و همان قاعده‌ای که §۰ می‌گذارد: «نمی‌دانم» هم‌ارز «متوقف شو» است. اگر تأیید بدهی، از گام ۰ شروع می‌کنم.
