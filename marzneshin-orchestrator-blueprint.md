# 🎯 Marzneshin Multi-Agent Orchestrator — Master Blueprint
## Implementation & Execution Specification based on BUILD-SPEC.md v2.0 (Executable Contract)

> **ورودی مرجع:** `BUILD-SPEC.md` v2.0 · `MASTER-PLAN v4.0 FINAL` · `ADR-001` تا `ADR-021` · `agents/cards/*.yaml`
> **محیط هدف:** Antigravity IDE (Multi-Agent Subagent Dispatch + CEO Orchestrator Pattern)
> **دستور شروع در چت جدید:** `/goal Execute Marzneshin Multi-Agent Orchestrator from marzneshin-orchestrator-blueprint.md`

---

## 🏗️ ۱) معماری ارکستراسیون (Hub-and-Spoke / CEO Pattern)

طبق بخش ۱۰.۱ و بخش ۲.۱ سند `BUILD-SPEC.md`، هیچ عاملی به تنهایی همه کارها را انجام نمی‌دهد. سیستم بر پایه تفکیک دقیق وظایف (Separation of Duties)، جداسازی کانتکست‌ها و تأیید دوطرفه (Two-Key Verification) بنا شده است:

```
                          ┌───────────────────────────┐
                          │   🎩 ORCHESTRATOR         │
                          │   (CEO Agent — Tier 0)    │
                          │                           │
                          │  • Routing & Task Decomp  │
                          │  • Lease & Fencing Tokens │
                          │  • Budget Reservation     │
                          │  • Escalation Management  │
                          │  • FORBIDDEN: Direct Edit │
                          └─────────────┬─────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │
    ┌──────▼──────┐              ┌──────▼──────┐              ┌──────▼──────┐
    │  ⚙️ Config   │              │  🛡️ Security │              │  🖥️ Infra   │
    │  Engineer   │              │  & Compliance│              │  SRE        │
    │  (Tier 0)   │              │  (Tier 0)    │              │  (Tier 0)   │
    │             │              │              │              │             │
    │  Autonomy L2│              │  Autonomy L1 │              │  Autonomy L1│
    │  configs/** │              │  security/** │              │  infra/**   │
    └──────┬──────┘              └──────┬──────┘              └──────┬──────┘
           │                            │                            │
           └────────────────────────────┼────────────────────────────┘
                                        │
                                        ▼
                          ┌───────────────────────────┐
                          │  ⚖️ TWO-KEY VERIFICATION   │
                          ├───────────────────────────┤
                          │ 🧪 QA Gate (L3)           │
                          │    verify.py + tests      │
                          │                           │
                          │ 🕵️ Adversarial Reviewer   │
                          │    Independent Lineage    │
                          │    Raw Evidence Audit     │
                          └─────────────┬─────────────┘
                                        │
                         (هر دو سبز = مجاز به ثبت)
                                        │
                                        ▼
                          ┌───────────────────────────┐
                          │  📜 HANDOFF GUARDIAN      │
                          │  (Tier 0 — Continuity)    │
                          │                           │
                          │  • Emit Canonical Receipt │
                          │  • Chain Hash Validation  │
                          │  • Rewrite HANDOFF.md     │
                          │  • Release Lease          │
                          └───────────────────────────┘
```

---

## 🎭 ۲) تیم ایجنت‌های تخصصی (Tier 0 & Tier 1)

مشخصات دقیق این ۸ ایجنت مستقیماً از کارت‌های رسمی در مخزن (`agents/cards/*.yaml`) استخراج شده است:

### ۲.۱) ایجنت ارکستراتور — `@orchestrator` (CEO Agent)
- **نقش:** رهبری تیم، تفکیک وظایف، تخصیص Lease و Fencing Token، مدیریت بودجه و ارجاع خطاها.
- **سطح استقلال (Autonomy):** پیش‌فرض L2، حداکثر L3 (عملیات زیرساخت/مالی سقف L1).
- **قلمرو مالکیت (`owns`):** `state/a2a/**`، `state/locks/**`
- **ممنوعیت‌های قطعی (Forbidden):**
  1. دستکاری مستقیم کد و کانفیگ در Data Plane.
  2. تأیید کار و خروجی خودش (Self-Approval ممنوع).
  3. دور زدن یا لغو Kill Switch.
- **مالک Counter-KPI:** ایجنت `adversarial-reviewer` (جلوگیری از انباشت صف و تأخیر در ارجاع).

### ۲.۲) مهندس کانفیگ — `@config-engineer`
- **نقش:** چرخه کنترل و انتشار کانفیگ‌های مرزنشین، اجرای Canary چندمرحله‌ای (۱٪ → ۱۰٪ → ۵۰٪ → ۱۰۰٪)، اجرای Rollback در صورت بروز خطا.
- **سطح استقلال:** L2
- **قلمرو مالکیت:** `configs/**`
- **ممنوعیت قطعی:** انتشار ۱۰۰٪ کانفیگ بدون گذراندن ارزیابی آماری Canary و Probeهای معتبر.

### ۲.۳) بازبین خصمانه — `@adversarial-reviewer` (کلید دوم Two-Key)
- **نقش:** بررسی نقادانه تمام تغییرات مسیر بحرانی، بازبینی شواهد خام (نه خروجی ایجنت اول)، ممیزی ادعاها و جلوگیری از Metric Gaming.
- **تبار (Lineage):** مستقل از ایجنت پیاده‌ساز (استفاده از مدل یا زاویه دید مستقل).
- **سطح استقلال:** L3 برای رد کردن (Rejection)، L0 برای تأیید (نمی‌تواند به تنهایی چیزی را تصویب کند).
- **ممنوعیت قطعی:** نوشتن کد در Production، تأیید تغییری که خودش پیشنهاد داده است.

### ۲.۴) گیت کنترل کیفیت — `@qa-gate` (کلید اول Two-Key)
- **نقش:** اجرای سوئیت تست‌ها، اعتبارسنجی اسکیماها، اجرای `python3 scripts/verify.py` و `scripts/sim.py`، تولید رأی نهایی با شواهد عینی.
- **سطح استقلال:** L3
- **قلمرو مالکیت:** `qa/**`، `artifacts/qa/**`
- **ممنوعیت قطعی:** تأیید کار خود؛ دستکاری گیت‌های تست بدون بازبینی خصمانه.

### ۲.۵) امنیت و انطباق — `@security-compliance`
- **نقش:** جلوگیری از نشت Secret، بررسی آسیب‌پذیری‌ها، ممیزی سیاست‌های امنیتی و دفاع در برابر Prompt Injection (§۱۵.۲).
- **سطح استقلال:** L1 (همیشه نیازمند نظارت).
- **قلمرو مالکیت:** `security/**`، `security/compliance/**`
- **ممنوعیت قطعی:** دور زدن فرآیند ۴ چشم؛ تغییر در خط‌مشی‌های انطباق قانونی.

### ۲.۶) نگهبان تداوم — `@handoff-guardian`
- **نقش:** تضمین اصل «هیچ سشنی بدون HANDOFF بسته نمی‌شود»، بازنویسی `state/HANDOFF.md`، پاکسازی Leaseهای زامبی، راستی‌آزمایی زنجیره رسیدها (`receipts/`).
- **سطح استقلال:** L3
- **قلمرو مالکیت:** `state/HANDOFF.md`، `state/leases/**`
- **ممنوعیت قطعی:** پایان دادن به سشن بدون HANDOFF معتبر؛ لغو Lease فعال و سالم.

### ۲.۷) مهندس زیرساخت و پایداری — `@infra-sre`
- **نقش:** پایش نودها، نود پروویژنینگ، ظرفیت، مدیریت حوادث و کاهش زمان بازیابی (MTTR).
- **سطح استقلال:** L1
- **قلمرو مالکیت:** `infra/**`
- **ممنوعیت قطعی:** اعمال تغییرات زیرساختی بدون تأیید Plan.

### ۲.۸) مهندس داده و تحلیل — `@analytics-engineer`
- **نقش:** تکامل تاکسونومی رویدادها، اعتبارسنجی JSON Schemaها، Upcasterها و سلامت متریک ستاره قطبی (NSM).
- **سطح استقلال:** L2
- **قلمرو مالکیت:** `analytics/**`
- **ممنوعیت قطعی:** تغییر تعریف متریک NSM بدون ADR؛ حذف فیلد بدون Upcaster معتبر.

---

## 🔁 ۳) پروتکل اجرای جلسات (The 9-Step Iron Protocol)

هر تسکی که توسط ارکستراتور در Antigravity IDE هدایت می‌شود، موظف به رعایت دقیق ۹ گام بخش ۰ سند `BUILD-SPEC.md` است:

```
[1. SYNC]      → خواندن state/STATE.json + HANDOFF.md + وضعیت kill switch
[2. GAP SCAN]  → اندازه‌گیری فاصله وضعیت فعلی تا Definition of Done
[3. CLAIM]     → ثبت Lease با fencing token جدید در state/leases/
[4. PLAN]      → تدوین برنامه حداکثر در ۷ گام شفاف همراه با آرتیفکت مشخص
[5. SIM]       → اجرای سناریوی تست در sim/ (قرمز = ورود به Production ممنوع)
[6. EXECUTE]   → تولید کد/کانفیگ واقعی و عملیاتی (نه شبه‌کد و نه TODO)
[7. VERIFY]    → اجرای تست و استخراج خروجی واقعی (verify.py)
[8. EMIT]      → ثبت Event + رسید (Receipt با prev_receipt_hash)
[9. HANDOFF]   → بازنویسی کامل HANDOFF.md و آزادسازی Lease
```

---

## 🛡️ ۴) پنج قانون آهنین (The Five Iron Rules)

1. **قانون رسیدها:** هیچ تغییری در هیچ کجای سیستم Done تلقی نمی‌شود مگر آنکه رسید معتبر با `prev_receipt_hash` در `receipts/` ثبت شده باشد.
2. **قانون اسکیماهای استاندارد:** تمام تغییرات وضعیت از طریق Schemas معتبر و قراردادهای داده کانونی اعمال می‌شوند.
3. **قانون تداوم:** در انتهای هر جلسه کاری، فایل `state/HANDOFF.md` باید مجدداً بازنویسی شود.
4. **قانون Fail-Closed:** در صورت وقوع هرگونه خطای ناشناخته، قطع ارتباط یا ناخوانا بودن کنترل ایمنی، کلید قطع اضطراری فعال شده و عملیات متوقف می‌شود («نمی‌دانم» = «متوقف شو»).
5. **قانون اثبات در شبیه‌ساز:** هر قابلیت و رفتاری قبل از ورود به پروداکشن، باید در محیط `sim/` با Seed قطعی اثبات و پاس شود.

---

## 🚀 ۵) نحوه اجرا در Antigravity IDE

### روش اول: اجرای کاملاً مستقل با دستور `/goal` (پیشنهادی)
در یک چت جدید در Antigravity IDE، دستور زیر را ارسال کنید:

```text
/goal Execute Marzneshin Multi-Agent Orchestrator according to marzneshin-orchestrator-blueprint.md and BUILD-SPEC.md v2.0. Act as the CEO Orchestrator: enforce the 9-step session protocol, delegate tasks to Tier 0 specialist agents in isolated contexts, enforce Two-Key verification (QA Gate + Adversarial Reviewer), verify baseline with verify.py, and emit canonical receipts. Do not stop until all steps are complete and verified.
```

### روش دوم: اجرای تعاملی در چت جدید
فایل `marzneshin-orchestrator-blueprint.md` را با `@` تگ کرده و بنویسید:

```text
طبق سند marzneshin-orchestrator-blueprint.md و با پایبندی به BUILD-SPEC.md v2.0:
۱. در نقش Orchestrator (CEO Agent) پروتکل ۹ مرحله‌ای (SYNC تا HANDOFF) را فعال کن.
۲. ساب‌ایجنت‌های تخصصی Tier 0 (شامل config-engineer، adversarial-reviewer، qa-gate و...) را در کانتکست‌های ایزوله با invoke_subagent دیسپچ کن.
۳. قبل از هرگونه ادغام، تأیید دوطرفه (Two-Key) از qa-gate و adversarial-reviewer اخذ کن.
۴. در پایان رسید جدید صادر کرده و HANDOFF.md را به‌روزرسانی کن.
```

---

## 📊 ۶) مانیتورینگ، رهگیری و لاگ‌ها
- **بررسی سلامت سیستم:** `python3 scripts/verify.py`
- **بررسی زنجیره رسیدها:** بررسی پوشه `receipts/` و فایل `state/events/`
- **مشاهده ساب‌ایجنت‌ها در Antigravity:** تایپ دستور `/agents`

---

## ⚡ ۷) ادغام کامل با Superpowers، اکوسیستم مهارت‌ها (۲۶۵ اسکیل) و MCPها

ارکستراتور موظف است تمام قابلیت‌ها و ابزارهای تعریف‌شده در پروژه را بر اساس ماتریس زیر فراخوانی و به کار گیرد:

### ۷.۱) چرخهٔ Superpowers (اجباری قبل از هر اکشن):
1. **ایده‌پردازی و تحلیل:** فراخوانی مهارت rainstorming قبل از هر تصمیم معماری.
2. **برنامه‌ریزی:** فراخوانی مهارت writing-plans برای تولید پلن‌های مرحله‌ای با گام‌های قطعی.
3. **توسعه به روش TDD:** ساب‌ایجنت‌ها موظف به رعایت چرخه RED-GREEN-REFACTOR با مهارت 	est-driven-development هستند.
4. **اشکال‌زدایی روش‌مند:** در صورت بروز هرگونه خطا، فراخوانی systematic-debugging (بررسی ۴ فاز ریشه‌ای).
5. **اعتبارسنجی قبل از اعلام پایان:** مهارت erification-before-completion قبل از هرگونه ادعای Done بودن.
6. **دیسپچ ساب‌ایجنت‌ها:** استفاده از dispatching-parallel-agents و subagent-driven-development.

### ۷.۲) بهره‌برداری On-Demand از ۲۶۵ مهارت پروژه (.agents/skills/):
هر ساب‌ایجنت متناسب با تخصص خود موظف به بارگذاری اسکیل‌های مربوطه است:
- **@config-engineer:** بارگذاری 
etwork-config-validation، docker-patterns، service-health.
- **@security-compliance:** بارگذاری security-review، security-scan، hipaa-compliance، prompt-optimizer.
- **@qa-gate:** بارگذاری erification-loop، 	dd-workflow، eval-harness، e2e-testing.
- **@analytics-engineer:** بارگذاری schema-mapping، data-autocleaning، database-migrations.
- **@infra-sre:** بارگذاری homelab-wireguard-vpn، 
etmiko-ssh-automation، kubernetes-patterns.

### ۷.۳) اتصال به سرورهای فعال MCP:
- **moxt:** خواندن/نوشتن فایل‌ها و تعامل با Control Room.
- **memwal:** ثبت و فراخوانی حافظه پایدار بین جلسات.
- **kimi-moe:** موتور استدلال عمیق محلی برای تحلیل‌های سنگین.
- **graphify:** کوئری روی گراف وابستگی کل مخزن و ردیابی وابستگی‌ها.
- **headroom:** فشرده‌سازی خروجی‌ها و بهینه‌سازی کانتکست ساب‌ایجنت‌ها.
- **codeburn:** ممیزی مصرف بودجه توکن و جلوگیری از هدررفت منابع.
