# 🚀 راهنمای جامع و گام‌به‌گام (Walkthrough): پیاده‌سازی و بهره‌برداری از OpenAI Codex for OSS
## پروژه Marzneshin Agent OS (`agentmemory`)

این مستند، راهنمای جامع و عملیاتی شما برای اتصال پروژه به برنامه رسمی **OpenAI Codex for Open Source**، فعال‌سازی اشتراک رایگان ۶ ماهه تا ۱ ساله ChatGPT Pro با دسترسی Codex، و راه‌اندازی چرخه کامل اتوماسیون مخزن است.

---

## 📌 بخش ۱: نمای کلی و دستاوردهای برنامه

بر اساس اطلاعات رسمی صفحه [OpenAI Codex for Open Source](https://developers.openai.com/community/codex-for-oss) و ویدیوی تحلیلی اینستاگرام:
1. **اشتراک رایگان ChatGPT Pro (به مدت ۶ ماه الی ۱ سال):**
   - دسترسی کامل به قابلیت‌های پیشرفته Codex، مدل‌های استدلال عمیق `o3-mini` و `gpt-4o` با سقف توکن بالا.
2. **اعتبار API رایگان از صندوق ۱ میلیون دلاری (Codex Open Source Fund):**
   - تخصیص کردیت ماهانه جهت اجرای خودکار ربات در گیت‌هاب اکشنز (GitHub Actions) برای تست، بازبینی PRها و ساخت پچ‌ها.
3. **دسترسی ویژه به Codex Security:**
   - ابزار تخصصی اسکن عمیق امنیتی کدها برای جلوگیری از نشت کلیدها و آسیب‌پذیری‌های Zero-Day.

---

## 🛠️ بخش ۲: اجزای پیاده‌سازی‌شده در این پروژه

تمام فایل‌ها و زیرساخت‌های لازم به صورت مهندسی‌شده و منطبق بر تفکر سیستمی در پروژه شما ایجاد شده‌اند:

```
marzneshin-agent-os/
├── .codex/
│   ├── config.toml                     # پیکربندی اتصال به Codex، MCPها و مدل‌ها
│   └── agents/
│       ├── codex-pr-automator.toml      # عامل خودکار ایجاد PR و حل Issueها
│       ├── codex-security.toml          # عامل اسکن امنیتی Codex Security
│       ├── receipt-auditor.toml         # عامل ممیزی رسیدهای رمزنگاری‌شده
│       ├── security-reviewer.toml       # عامل ناظر محرمانگی توکن‌ها و IPC
│       └── watchdog-reviewer.toml       # عامل نظارت بر سلامت سرویس‌ها
├── .github/workflows/
│   ├── codex-oss-pr-review.yml          # گیت‌هاب اکشن برای Review خودکار و گیت امنیتی
│   └── codex-maintainer-automation.yml  # گیت‌هاب اکشن برای حل Issueها با دستور /codex
├── scripts/
│   ├── codex_bridge.py                  # موتور واسط پایتون بین مخزن و Codex
│   ├── pr.py                            # ابزار مدیریت PR با بررسی شروط verify.py
│   └── review.py                        # بازبین خصمانه (Adversarial Reviewer)
├── tests/
│   └── test_codex_bridge.py             # تست‌های واحد موتور واسط (۱۰۰٪ پاس شده)
└── docs/
    ├── codex-oss-systems-thinking-map.md # نقشه کامل تفکر سیستمی و مدل علی-معلولی
    ├── codex-oss-application-dossier.md  # فرم و متن آماده جهت ارسال به OpenAI
    └── codex-oss-walkthrough.md          # همین راهنمای گام‌به‌گام
```

---

## 📝 بخش ۳: راهنمای گام‌به‌گام ثبت‌نام و دریافت اعتبارات رایگان

برای دریافت ۶ ماه اشتراک رایگان Pro و اعتبارات صندوق ۱ میلیون دلاری، مراحل زیر را طی کنید:

### گام اول: ورود به پرتال OpenAI
1. وارد لینک زیر شوید:
   👉 [https://developers.openai.com/community/codex-for-oss](https://developers.openai.com/community/codex-for-oss)
2. بر روی دکمه **Apply today** کلیک کنید.
3. با اکانت OpenAI خود وارد شوید.

### گام دوم: پر کردن فرم درخواست با اطلاعات آماده‌شده
از متن آماده‌شده در فایل `docs/codex-oss-application-dossier.md` استفاده کنید:
- **Project Name:** `Marzneshin Agent OS`
- **Repository URL:** لینک مخزن گیت‌هاب خود را وارد کنید (مطمئن شوید ریپازیتوری Public است و فایل `LICENSE` از نوع MIT دارد).
- **Project Description:** متن بخش ۲ فایل `codex-oss-application-dossier.md` را کپی کنید.
- **Workflow & Automation Plan:** متن بخش ۳ را کپی کنید که دقیقاً توضیح می‌دهد پروژه چگونه از `.github/workflows/codex-oss-pr-review.yml` و ابزارهای `.codex/` استفاده می‌کند.
- **Security & Two-Key Verification:** متن بخش ۴ را قرار دهید که نشان‌دهنده معماری فوق‌العاده امن سیستم است.

> 💡 **نکته کلیدی تأیید:** ارزیابان OpenAI به دنبال پروژه‌هایی هستند که واقعاً از ابزارهای اتوماسیون (مانند گیت‌هاب اکشنز و کانفیگ Codex) استفاده می‌کنند. وجود پوشه `.codex/` و فایل‌های Action در مخزن شما، شانس قبولی درخواست را به حداکثر می‌رساند!

---

## ⚙️ بخش ۴: فعال‌سازی در GitHub Repository

پس از دریافت تأییدیه و کلید API:

### ۱. تنظیم Secrets در گیت‌هاب:
وارد تنظیمات مخزن در گیت‌هاب شوید:
`Settings -> Secrets and variables -> Actions -> New repository secret`
دو متغیر زیر را تعریف کنید:
1. `OPENAI_API_KEY`: کلید API اختصاص‌یافته توسط OpenAI Codex OSS Fund.
2. `GITHUB_TOKEN`: به صورت پیش‌فرض توسط خود گیت‌هاب اکشنز فراهم است (یا در صورت نیاز Personal Access Token با دسترسی `repo`).

### ۲. اعطای دسترسی نوشتن به اکشنز (Workflow Permissions):
در گیت‌هاب به مسیر زیر بروید:
`Settings -> Actions -> General -> Workflow permissions`
گزینه **Read and write permissions** را فعال کرده و تیک **Allow GitHub Actions to create and approve pull requests** را بزنید.

---

## 🏃 بخش ۵: سناریوهای استفاده و اجرای عملیاتی

### سناریو ۱: تست سلامت محلی سیستم با موتور واسط (Local Verification)
در محیط لینوکس/WSL ترمینال پروژه، دستور زیر را اجرا کنید:
```bash
python3 scripts/codex_bridge.py verify
```
خروجی مورد انتظار:
```text
==> Checking Marzneshin Agent OS Invariants...
✅ Invariant Verification Gate PASSED.
```

### سناریو ۲: بررسی تست‌های واحد موتور واسط
```bash
python3 -m unittest tests.test_codex_bridge
```
خروجی:
```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.006s

OK
```

### سناریو ۳: بازبینی خودکار پول‌ریکوئست‌ها (Autonomous PR Review)
هنگامی که هر کانتریبیوتری یک PR باز می‌کند:
1. گیت‌هاب اکشن `.github/workflows/codex-oss-pr-review.yml` فعال می‌شود.
2. گیت امنیتی `scripts/verify.py --all` اجرا می‌شود.
3. بازبین خصمانه `scripts/review.py check` محرمانگی و عدم دستکاری خطوط حیاتی را بررسی می‌کند.
4. واسط Codex کدهای تغییریافته را اسکن کرده و کامنت تحلیلی ثبت می‌کند.

### سناریو ۴: حل خودکار Issue با دستور متنی در کامنت گیت‌هاب
کافی است در هر Issue در گیت‌هاب کامنت بگذارید:
```text
/codex fix the watchdog health check regression
```
یا
```text
@codex please inspect configs/services.json and generate a patch
```
گردش کار `.github/workflows/codex-maintainer-automation.yml` اجرا شده، کد تغییر را می‌نویسد، تست‌ها را پاس می‌کند و یک PR آماده به همراه رسید رمزنگاری‌شده باز می‌کند!

---

## 🌟 بخش ۶: جمع‌بندی تفکر سیستمی
با این پیاده‌سازی:
- **سیکل تقویت‌کننده (R1):** مخزن شما فعال‌تر شده، ستاره و مشارکت بالاتر می‌رود و سهمیه بیشتری از OpenAI دریافت می‌کنید.
- **سیکل خودترمیمی (R2):** باگ‌ها به صورت خودکار پچ شده و تست‌ها قبل از مرج اجرا می‌شوند.
- **سیکل تعادل و پایداری (B1 و B2):** اصول Karpathy، اصل تأیید دوطرفه (Two-Key) و بررسی‌های نامتغیرها مانع از ورود کدهای معیوب به سیستم می‌شوند.
