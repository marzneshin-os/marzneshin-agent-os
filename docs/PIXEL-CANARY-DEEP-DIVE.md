# 🔍 Deep Dive: Pixel Canary & Next.js Agent Evals Benchmark Suite

> **Status:** Production-Ready & Integrated  
> **Date:** September 2026  
> **Source:** [nextjs.org/evals](https://nextjs.org/evals) · [cline.bot/desktop](https://cline.bot/desktop) · Vercel AI Gateway  
> **Evaluation Metric:** Success Rate (pass@4) on Next.js 15+ Engineering Tasks  

---

## 1. Executive Summary & Overview (خلاصه مدیریتی)

در اواخر سپتامبر ۲۰۲۶، یک مدل هوش مصنوعی مخفیانه و مرموز به نام **Pixel Canary** (`stealth/pixel-canary`) از طریق گیت‌وی هوش مصنوعی ورسل (**Vercel AI Gateway**) منتشر شد که توجه جامعه مهندسی نرم‌افزار و توسعه‌دهندگان عامل‌های خودگردان (Autonomous AI Agents) را به خود جلب کرد.

بر اساس ارزیابی رسمی بنچمارک **Next.js Agent Evals (pass@4)**:
* مدل **Pixel Canary** موفق به کسب نرخ موفقیت **۹۰.۰٪** (در حالت پایه) شده و توانسته است شانه به شانه غول پرهزینه **GPT 6 Astra (High)** (با نرخ ۹۰.۰٪ و هزینه $0.89 به ازای هر تسک) قرار گیرد.
* با ارائه کانتکست ساختاریافته پروژه از طریق فایل‌های راهنما (`AGENTS.md` / `BUILD-SPEC.md`)، این نرخ موفقیت تا **۹۶.۸٪** ارتقا می‌یابد.
* مهم‌ترین مزیت رقابتی Pixel Canary: **کاملاً رایگان (FREE - $0.00)** بودن آن در دوره پیش‌نمایش مخفی (Stealth) است، در حالی که رقبای تجاری آن هزینه‌های سنگینی (از $0.28 تا $0.89 به ازای هر تسک) تحمیل می‌کنند.
* دسترسی مستقیم به این مدل هم‌اکنون از طریق نسخه بومی دسکتاپ عامل محبوب **Cline** به آدرس [cline.bot/desktop](https://cline.bot/desktop) و همچنین اکستنشن‌های محیط توسعه فعال است.

---

## 2. Official Next.js Agent Evals Benchmark (نتایج بنچمارک رسمی)

| Rank | Model Name | pass@4 Success Rate | Cost / Task (USD) | Relative Value / Cost Efficiency | Status / Deployment |
| :---: | :--- | :---: | :---: | :---: | :--- |
| 🥇 | **Claude Fable 5.1 (high)** | **97%** | $0.72 | Premium Quality ($0.74/pt) | Production API |
| 🥈 | **Pixel Canary** | **90%** | **$0.00 (FREE)** | **Infinite ROI (0.00 cost)** | **Stealth Gateway / Cline** |
| 🥈 | **GPT 6 Astra (high)** | **90%** | $0.89 | High Cost ($0.99/pt) | Commercial API |
| 🥉 | **Kimi K3** | **84%** | $0.28 | Budget Runner ($0.33/pt) | Commercial API |
| 5 | **Claude Sonnet 5** | **81%** | $0.39 | Standard Tier ($0.48/pt) | Commercial API |

### 📊 Benchmark Tasks Architecture
بنچمارک Next.js Agent Evals شامل چالش‌های پیچیده دنیای واقعی فریمورک Next.js است:
1. **NEXT-01 (Server Actions):** اعتبارسنجی فرم‌ها با Zod، تراکنش‌های امن دیتابیس و پاک‌سازی کش با `revalidatePath`.
2. **NEXT-02 (RSC Streaming):** رندر استریمینگ در سمت سرور و استفاده بهینه از Suspense Skeleton.
3. **NEXT-03 (Hydration Mismatch):** برطرف‌سازی خطاهای تطابق هیدریشن کلاینت/سرور در تم‌ها و ساعت سیستم.
4. **NEXT-04 (Edge Handlers):** مسیریاب‌های لبه با احراز هویت JWT و هدرهای امنیتی استاندارد.
5. **NEXT-05 (Intercepting Routes):** مدال‌های موازی و مسیرهای مسدودکننده (`(.)photo/[id]`).
6. **NEXT-06 (Next.js 15 Async APIs):** مهاجرت کدهای سنکرون به فرمت غیرهمگام `await params` و `await cookies()`.

---

## 3. Cost Analysis & Economic ROI (تحلیل اقتصادی و صرفه‌جویی)

در لوپ‌های عامل‌های خودگردان (Multi-Agent Workflows) که صدها یا هزاران تسک کدنویسی در روز اجرا می‌شود، تفاوت هزینه سرسام‌آور است:

* **صرفه‌جویی در برابر GPT 6 Astra (به ازای ۱,۰۰۰ تسک):**
  $$\text{Savings} = 1,000 \times \$0.89 - \$0.00 = \$890.00$$
* **صرفه‌جویی در برابر Claude Fable 5.1 (به ازای ۱,۰۰۰ تسک):**
  $$\text{Savings} = 1,000 \times \$0.72 - \$0.00 = \$720.00$$
* در مقیاس **۱۰,۰۰۰ تسک مهندسی**: صرفه‌جویی مالی بالغ بر **$۸,۹۰۰ دلار** به ازای هر ماه خواهد بود.

---

## 4. Privacy & Zero Data Retention (ZDR) Warning (هشدارهای امنیتی)

> [!WARNING]
> بر اساس اعلام رسمی Vercel، مدل Pixel Canary در فاز آزمایشی و رایگان خود **فاقد تعهد Zero Data Retention (ZDR)** است. ورودی‌ها و خروجی‌های مدل ممکن است برای بهبود و آموزش مدل استفاده شوند.

### دستورالعمل امنیتی سیستم‌عامل مرزنشین (Marzneshin Security Policy):
1. **عدم ارسال کلیدهای محرمانه:** هرگز API Key، توکن‌های JWT یا پسوردهای پروداکشن به این مدل ارسال نمی‌شود.
2. **سندباکس و پاک‌سازی خودکار:** آداپتور `adapters/pixel_canary.py` کدهای حساس و متغیرهای محرمانه را قبل از ارسال فیلتر و ردکت (Redact) می‌کند.
3. **استفاده بهینه برای تولید کامپوننت و تست:** مناسب برای نوشتن تست‌های واحد، کامپوننت‌های بصری، تسک‌های App Router و ریفکتورینگ عمومی کد.

---

## 5. Cline Desktop Integration (اتصال مستقیم به کلین)

پروژه **Cline Desktop** ([cline.bot/desktop](https://cline.bot/desktop)) یک اپلیکیشن بومی و مستقل است که بدون نیاز به VS Code کار می‌کند.

### نحوه فعال‌سازی در سیستم:
اسکریپت خودکار زیر در ریپازیتوری آماده شده و کل تنظیمات کلاینت را بدون نیاز به مداخله دستی پیکربندی می‌کند:

```bash
# تنظیم خودکار و فعال‌سازی به عنوان مدل پیش‌فرض
python3 scripts/setup_cline_pixel_canary.py --activate
```

تنظیمات اعمال شده در `~/.cline/data/settings/providers.json`:
```json
{
  "provider": "openai-compatible",
  "model": "stealth/pixel-canary",
  "baseUrl": "https://ai-gateway.vercel.sh/v1",
  "apiKey": "free",
  "headers": {
    "HTTP-Referer": "https://marzneshin.os",
    "X-Title": "Marzneshin Autonomous OS"
  }
}
```

---

## 6. Repository Components (کامپوننت‌های پیاده‌سازی شده در پروژه)

1. **`adapters/pixel_canary.py`**: آداپتور رسمی دارای کلید Idempotency، Circuit Breaker، پشتیبانی از شبیه‌سازی (Sim-First) و کال‌های شبکه واقعی با فال‌بک امن.
2. **`configs/router.json`**: ثبت در کامبوهای استراتژیک سیستم: `nextjs-evals`، `free-mega`، `smart`، `antigravity` و `fable-flash`.
3. **`dashboards/nextjs-agent-evals/`**: داشبورد مدرن تحت وب (Dark Mode Glassmorphism) روی پورت **8089**:
   - چارت داینامیک مطابق تصویر بنچمارک
   - ماشین‌حساب تعاملی صرفه‌جویی ROI
   - شبیه‌ساز زنده تست‌های Next.js
   - دکمه‌های کپی تنظیمات Cline و سوییچر زبان
4. **`eval/nextjs_agent_evals.py`**: سوئیت ارزیابی دقیق تسک‌های بنچمارک و متریک‌های pass@4.
5. **`scripts/setup_cline_pixel_canary.py`**: اتوماسیون کامل پیکربندی Cline Desktop و اکستنشن.
6. **`tests/test_pixel_canary_adapter.py`** & **`tests/test_nextjs_agent_evals.py`**: تست‌های جامع و تضمین کیفیت ۱۰۰٪ سبز.
