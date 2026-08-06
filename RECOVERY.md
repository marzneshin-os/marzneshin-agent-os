# RECOVERY — مسیر خروج انسانی (غیرفنی) — BUILD-SPEC §11.2

> این سند برای یک نفر **غیرفنی** نوشته شده که باید بتواند سیستم را متوقف یا واگذار کند.
> یک نسخهٔ رمزنگاری‌شده از این فایل + دسترسی‌ها در بستهٔ escrow روزانهٔ workflow `mirror` قرار می‌گیرد.
> به زبان ساده: اگر کسی که این سیستم را ساخته در دسترس نیست، این صفحه راه نجات است.

---

## ۱) توقف فوری سیستم (مهم‌ترین بخش)

سیستم پنج راه توقف دارد. **از هر راهی که برایتان ساده‌تر است، یکی کافی است:**

### راه الف — ساده‌ترین، بدون هیچ ابزاری (K3)
1. وارد Moxt شوید (همان workspace پروژه).
2. Workflow «Control Room» را باز کنید.
3. Task «Kill Switch» را به وضعیت **Engaged** ببرید.
4. سیستم ظرف حداکثر ۱۵ دقیقه متوقف می‌شود (workflow `heartbeat` این وضعیت را به فایل توقف می‌ریزد).

### راه ب — با کامپیوتر، بدون دانش برنامه‌نویسی (K1)
1. مخزن `marzneshin-ops` را در GitHub باز کنید.
2. فایل `state/KILL` را بسازید (دکمهٔ Add file) با این محتوا:
   ```json
   {"entries": [{"scope": "global", "target": null, "reason": "manual stop by owner",
                 "engaged_at": "2026-01-01T00:00:00.000Z", "engaged_by": "owner", "source": "K1"}]}
   ```
3. Commit کنید. سیستم در اولین بررسی (کمتر از چند دقیقه) متوقف می‌شود.

### راه ج — خط فرمان (K4)
```bash
python3 scripts/killswitch.py engage global --reason "manual stop" --by <your-name>
```
برای بررسی وضعیت: `python3 scripts/killswitch.py status`

### راه د — GitHub Settings (K2)
Settings → Secrets and variables → Actions → Variables → `KILL_SWITCH` = `global`

### راه ه — خودکار (K5)
سیستم خودش در این موارد متوقف می‌شود: نقض SLO بحرانی · هزینه > ۳× حد عادی ·
۳ heartbeat پیاسی گم‌شده · الگوی خطای غیرعادی · هشدار امنیتی.

> **نکتهٔ مهم:** اگر سیستم «نمی‌داند» وضعیت توقف چیست (مثلاً هیچ‌کدام از راه‌ها پاسخ ندهد)،
> خودش به‌صورت پیش‌فرض متوقف می‌ماند. این ویژگی است، نه نقص: «نمی‌دانم» = «متوقف شو».

---

## ۲) راه‌اندازی مجدد پس از توقف

فقط انسانی و فقط آگاهانه (همیشه با یک یادداشت تصمیم در `decisions/ADR/`):
```bash
python3 scripts/killswitch.py release global --by <your-name>
```
یا Task «Kill Switch» در Moxt را به «Clear» ببرید.

---

## ۳) دسترسی‌ها و نحوهٔ باطل‌کردن آن‌ها

| دسترسی | کجاست | چطور باطل شود |
| ---| ---| --- |
| GitHub repo | github.com/<org>/marzneshin-ops | Settings → Manage access |
| GitHub Actions tokens | OIDC، بدون secret بلندعمر | حذف workflowها یا بستن repo |
| Moxt workspace | moxt.ai | Workspace settings → Members |
| Tokenهای Adapter (Marzneshin/پرداخت/…) | Vault/SOPS (جزئیات در `security/`) | rotation در همان سرویس |
| کانال هشدار خارج از باند | Slack/Telegram (وقتی فعال شود) | حذف webhook/bot |

---

## ۴) واگذاری مالکیت (Succession)

پروتکل کامل ۷ مرحله‌ای در BUILD-SPEC §11.1 است و workflow `succession` آن را
خودکار اجرا می‌کند. خلاصه برای انسان:

1. **FREEZE** — کارهای در جریان مسدود و lease باطل می‌شود (خودکار).
2. **REVOKE** — دسترسی‌ها را طبق جدول بالا باطل کنید (دستی).
3. **RECONSTRUCT** — وضعیت از receipt chain و event log بازسازی می‌شود (خودکار)؛
   به حافظهٔ شخص قبلی اعتماد نکنید، به زنجیره اعتماد کنید.
4. **REASSIGN** — Orchestrator مالک جدید را با یک سطح autonomy کمتر تعیین می‌کند.
5. **VERIFY** — تا smoke test و sim سبز نشود، workstream در L1 می‌ماند.

---

## ۵) چه چیزی هرگز در این سیستم ذخیره نمی‌شود

- محتوای ترافیک کاربران و مقصد اتصال‌ها (ممنوع قانونی و اخلاقی — §۱۳.۱).
- هیچ secret یا کلید به‌صورت متن خام.
- دادهٔ بیش از حد لازم کاربر (حداقل داده + consent state در هر event).

## ۶) مخاطبان اضطراری

- مالک فعلی: pexabo (pexabo4345@aganseo.com)
- کانال خارج از باند: (هنگام فعال‌سازی در VS-4 اینجا ثبت می‌شود)

---

## ۷) باز کردن بستهٔ escrow (برای گیرندهٔ بسته)

بستهٔ روزانهٔ `mirror` به‌صورت رمزنگاری‌شده است (`escrow-YYYY-MM-DD.tar.gz.enc`).
رمز (passphrase) را فقط مالک فعلی دارد و باید برایتان بفرستد. باز کردن:

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in escrow-YYYY-MM-DD.tar.gz.enc | tar xz
```

یا با ابزار خود مخزن (که صحت محتوا و تازگی‌اش را هم می‌سنجد):

```bash
MARZ_ESCROW_PASSPHRASE="<passphrase>" python3 scripts/escrow.py verify escrow-YYYY-MM-DD.tar.gz.enc
```

اگر verify قرمز شد (drift یا hash mismatch)، به محتوای بسته اعتماد نکنید و از مالک
بستهٔ تازه بخواهید.
