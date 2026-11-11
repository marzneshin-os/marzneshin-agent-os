# HANDOFF

> وضعیت آخرین نشست کاری به‌صورت خوانا برای انسان. این فایل در پایان هر جلسه کاری بازنویسی می‌شود (Iron Rule 3).
> وضعیت ماشین: `STATE.json` + لاگ رویدادها (`state/events/`) + زنجیره رسیدها (`receipts/`).

> **شروع جلسه جدید؟ ابتدا [`../ONBOARDING.md`](../ONBOARDING.md) را مطالعه کنید.**
> پروتکل کامل Cold-Start، ترتیب مطالعه اسناد، نحوه آغاز جلسه FSP، اعتبارسنجی خط مبنا، نحوه انتخاب تسک بعدی، اقدامات ممنوعه و رویه الزامی پایان جلسه در آن مستند شده است.

- **Updated:** 2026-11-11
- **By:** antigravity-argon-architect (Gemini 3.8 Flash High / Antigravity Harness 2.0, session S-115231, fencing token 39)
- **Slice:** **VS-12 Post-Milestone Autonomous Operational Protocol** (Task **`T-0031`** / **`ADR-034`** Git Sync & Closeout)

---

## Where we are (وضعیت جاری و خلاصه اقدامات انجام‌شده)

معماری کامل **Harness 2.0 & Argon-Grade Deep Reasoning** از سند مرجع `https://share.gemini.google/qAjccclyXYOw` با تطبیق کامل بر SSoT مخزن، استاندارد `ADR-030` (Prefix Caching) و بودجهٔ زمانی هوک‌ها (`CLAUDE.md §6`) پیاده‌سازی، راستی‌آزمایی و با ریموت همگام‌سازی شد (`ADR-034`، رسید `T-0031`):

1. **همگام‌سازی با مخزن ریموت (`origin/main`):** دریافت و rebase تمیز ۱۳ کامیت ورودی ربات گیت‌هاب بدون تعارض و هم‌راستاسازی کامل شاخهٔ محلی با ریموت.
2. **تریاژ و بهداشت مخزن:** پاک‌سازی ۱۹ فایل موقت ساب‌ایجنت‌ها تحت `.agents/teamwork/`، حذف ردیابی ۱۶ فایل لاگ شلوغ از ایندکس گیت (`git rm --cached state/logs/*.log`) با حفظ آن‌ها روی دیسک، حذف کش موقت `state/web_memory/` و به‌روزرسانی اصولی `.gitignore` برای جلوگیری از آلودگی مجدد.
3. **هستهٔ شناختی همیشه فعال (`GEMINI.md`):** ادغام قوانین Boris Cherny، ابزارهای CLI عملیاتی و GRAVITAS با هستهٔ Harness 2.0 (مهار آسیب‌های Flash 3.8، خوانش کل‌نگر، بودجهٔ ۶۰/۲۰/۲۰، و اینواریانت‌های `I1`–`I17`).
4. **پیکربندی MCP و هوک‌های Antigravity (`.agents/mcp_config.json`, `.agents/hooks.json`):** اتصال هرمتیک `marzneshin-agentmemory` روی `./state`؛ اتصال هوک‌های `SessionStart`/`Stop` به `scripts/fsp.py status` و `PostToolUse` به حسگر سریع `scripts/verify.py --lint-imports --lint-clock` (~0.38s به‌جای `health.py --skip-sim` ۱۱۸ ثانیه‌ای).
5. **قوانین و مهارت‌ها (`.agents/rules/`, `.agents/skills/`, `.agents/agents/`):** افزودن `argon-deep-reasoning.md` (`model_decision`)، `marzneshin-code-invariants.md` (`glob`)، چهار مهارت `/fsp-start`، `/sim-tdd`، `/fsp-closeout`، `/scar-learn` و ممیز خواندنی `argon-critic.md` با حفظ کامل زیرماژول `.agents/skills/relevance-ai`.
6. **آشتی کلید توقف اضطراری (Kill Switch Reconcile):** بازگردانی وضعیت تمیز و اجرای `killswitch.py reconcile` برای رفع مقادیر تست و برقراری وضعیت `running (0 active)`، `L2 permitted=True` با شناسایی رسمی عامل `antigravity-argon-architect`.
7. **تست و ممیزی مستقل (`tests/test_argon_harness.py`, `ADR-034`):** ۷ تست جدید واحد، ممیزی `adversarial-reviewer` (PASS)، اسکن AgentShield (0 CRITICAL/HIGH)، گیت‌های `verify.py --all` (6/6) و مجموعهٔ کامل `health.py` (478/478 تست، 6/6 بررسی و 51/51 سناریوی شبیه‌سازی سبز).

---

## Baseline health

- **Unit tests:** 478 / 478 passing (`python3 scripts/health.py`)
- **Verification checks:** 6 / 6 passing (`python3 scripts/verify.py --all`)
- **Simulation scenarios:** 51 / 51 passing (`python3 scripts/sim.py run --all --seeds 11,27,43`)
- **Kill switch:** Running (`global=False`, `L2 permitted=True`, all sources clear)
- **Latest receipt:** `T-0031` (`chain_index: 33`)

---

## Misleading non-regressions observed

- در محیط WSL، اجرای `.venv/bin/python3 scripts/health.py` ۴ خطای import برای ماژول‌های `fastapi` و `langgraph` می‌دهد زیرا این وابستگی‌ها روی `python3` سیستم نصب هستند و نه داخل `.venv`؛ با `python3` سیستم همهٔ ۴۷۸/۴۷۸ تست سبز هستند.
- اجرای تست‌های واحد (به‌ویژه `test_gateway.py`) روی درخت کاری زنده، فایل‌های `state/KILL` و `state/KILL.heartbeat.json` را با هویت‌های تست (`test-operator` و `test-gateway`) تغییر می‌دهد؛ پس از اجرای `health.py`، بازیابی نسخه تمیز و اجرای `killswitch.py reconcile` برای پاکسازی الزامی است. در تسک بعدی (`T-0032`) باید با تعریف متغیر محیطی یا ایزوله‌سازی `MARZNESHIN_OPS_ROOT` در تست‌ها، از نوشتن تست‌ها روی `state/` زنده مخزن جلوگیری شود.
- همچنین Chrome remote debugging (`DevToolsActivePort`) در محیط ویندوز فعال نبود؛ خوانش لینک `share.gemini.google` با رندر ایزولهٔ headless Edge انجام شد.

---

## Open Owner blockers (Oxx)

- **O1:** تایید قیمت‌گذاری نهایی مدل‌ها برای `forecast()` دقیق بودجه (`TRADEOFF-REGISTER.md` T18).
- **O3:** کلید/توکن GitHub Actions برای اجرای زندهٔ برخی مسیرهای ازراه‌دور.
- **O4:** کانال هشدار خارج از باند (OOB) عملیاتی.
- **IDE Remote Debugging / Local Daemons:** در صورت نیاز به ساب‌ایجنت `browser` در چت‌های بعدی، فعال‌سازی `chrome://inspect/#remote-debugging` در Chrome و بررسی لاگ `agentmemory` (`state/logs/agentmemory.log`) و پورت `ccr` (`3456`/`3459`).

---

## Next session — start here

1. شروع تسک **`T-0032`**: ایزوله‌سازی `MARZNESHIN_OPS_ROOT` در تست‌های واحد پایتون تا اجرای `health.py` هیچ‌گاه فایل‌های زنده `state/` را آلوده نکند.
2. اجرای `/fsp-start` (یا `python3 scripts/fsp.py status && python3 scripts/health.py`) با `python3` سیستم.
3. پایش سلامت ۱۲ سرویس محلی با `python3 scripts/dev.py status` و فعال بودن تایمر نگهبان `marzneshin-watchdog.timer`.
