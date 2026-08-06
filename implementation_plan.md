# بازسازی ساختار مخزن (فاز ۰)

این برنامه شامل پاک‌سازی مخزن و انطباق آن با ساختار مشخص‌شده در §2.2 از BUILD-SPEC است.

## User Review Required

> [!WARNING]
> لطفاً حذف فایل‌ها و پوشه‌های زیر و انتقال فایل‌ها را تأیید کنید.

فایل‌ها و پوشه‌های زیر مربوط به اسکلت Next.js/v0 هستند و طبق دستور شما از ریشه مخزن **حذف** خواهند شد:
- `app/`
- `components/`
- `lib/`
- `public/` (شامل فایل `marzneshin-ops-handoff.zip` که کلاً حذف می‌شود)
- `components.json`
- `next.config.mjs`
- `package.json`
- `pnpm-lock.yaml`
- `postcss.config.mjs`
- `tsconfig.json`

همچنین هرگونه کش پایتون (`__pycache__/*.pyc`) از ردیابی گیت خارج و حذف می‌شود.

## Proposed Changes

### تغییرات ساختاری (جابجایی)

تمام محتوای پوشه `marzneshin-ops/` به ریشه مخزن (`./`) منتقل می‌شود. این محتوا شامل موارد زیر است:
- `BUILD-SPEC.md`, `CLAUDE.md`, `CODEOWNERS`, `CONTEXT-PACK.md`, `ONBOARDING.md`, `RECOVERY.md`
- پوشه‌های: `.github/`, `adapters/`, `agents/`, `analytics/`, `artifacts/`, `decisions/`, `hooks/`, `receipts/`, `scripts/`, `sim/`, `state/`, `tests/`

پس از انتقال، پوشه خالی `marzneshin-ops/` حذف خواهد شد.

### [MODIFY] .gitignore
محتوای `.gitignore` فعلی کاملاً با موارد زیر جایگزین می‌شود (فایل‌های `state/` ردیابی خواهند شد):
```text
.venv/
__pycache__/
*.pyc
.env*
node_modules/
.next/
```

## Verification Plan

### بررسی امنیتی (Secret Scan)
قبل از ثبت (commit) تغییرات، از طریق یک اسکریپت یا ابزار `gitleaks` (در صورت وجود) یا جستجوی الگوهای متداول، کل مخزن برای یافتن secretها اسکن می‌شود.
در صورت یافتن هرگونه secret، فرآیند متوقف شده و به شما گزارش داده می‌شود.

### کامیت (Commit)
در صورت تأیید شما و موفقیت در اسکن، تغییرات در یک کامیت مجزا با پیام زیر و محاسبه task id بعدی ثبت می‌شود:
`chore: restructure repo to BUILD-SPEC §2.2 layout (T-XXXX)`
