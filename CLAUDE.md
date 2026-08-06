# CLAUDE.md — قوانین پایدار Marzneshin Autonomous OS

> حاکم: `BUILD-SPEC.md` (v2.0). این فایل فقط قوانین پایدار و کوتاه است؛ جزئیات در همان سند.
> در تعارض، BUILD-SPEC حاکم است. زبان قواعد فارسی، شناسه‌ها و دستورها انگلیسی (D10).
>
> **اکانت/سشن جدید؟ اول [`ONBOARDING.md`](ONBOARDING.md) را بخوان** — پروتکل کاملِ cold-start.

## ۱) منبع حقیقت و چرخهٔ کار

- **GitHub تنها SSoT است** (I1). `STATE.json` مشتق است، نه منبع — از event log بازسازی می‌شود.
- شروع هر جلسه: `python3 scripts/fsp.py status` → `state/HANDOFF.md` → `CONTEXT-PACK.md` → killswitch.
- پروتکل نه‌مرحله‌ای FSP (§۰): SYNC → GAP SCAN → CLAIM → PLAN → SIM → EXECUTE → VERIFY → EMIT → HANDOFF.
- قبل از هر کار: `python3 scripts/fsp.py claim <workstream> --agent <id>` (TTL 90m، fencing token).
- پایان هر جلسه: بازنویسی `state/HANDOFF.md` + `python3 scripts/fsp.py release <workstream> --agent <id>`.

## ۲) قوانین آهنین

1. هیچ کانفیگی بدون QA به کاربر نمی‌رسد.
2. هیچ کمپینی بدون hypothesis و stop condition اجرا نمی‌شود.
3. هیچ جلسه‌ای بدون HANDOFF تمام نمی‌شود.
4. هیچ secretی وارد مخزن نمی‌شود — نه در کد، نه در event، نه در receipt، نه در log.
5. هیچ تصمیمی بدون owner، evidence و rollback پذیرفته نیست.
6. **«نمی‌دانم» هم‌ارز «متوقف شو» است.** هر کنترل ایمنی ناخوانا = فعال، نه غیرفعال (fail-closed).

## ۳) Invariantهای کلیدی (فهرست کامل: BUILD-SPEC §۱.۳)

- **I3** هر تسک دقیقاً یک receipt دارد با `status` معتبر؛ `hooks/task_complete.py` بدون receipt exit 1.
- **I6** هیچ secret خامی: `lib/redact.py` در event/receipt/همهٔ hookها.
- **I7** هر تصمیم reversible: `rollback.tested=true` + `tested_at` + `tested_in`.
- **I11** هیچ کد/کانفیگ جدیدی بدون `sim_evidence` سبز به production نمی‌رود.
- **I12** همهٔ کنترل‌های ایمنی fail-closed: kill switch، lease، budget، probe.
- **I15** زنجیرهٔ receipt پیوسته: `python3 scripts/verify.py --chain` در هر PR.
- **I16** ورودی `untrusted` → سقف autonomy = L1، بدون استثنا.
- **I17** یک نویسنده به ازای هر مسیر: `owns` در Agent Card + پارتیشن event per-actor.

## ۴) دستورهای روزمره

```bash
python3 scripts/fsp.py status                 # SYNC
python3 scripts/fsp.py claim ws --agent id    # CLAIM (fencing token می‌دهد)
python3 scripts/verify.py --all               # دروازهٔ CI محلی
python3 scripts/compact.py                    # بازسازی STATE.json از events
python3 scripts/killswitch.py status          # وضعیت kill switch
python3 scripts/killswitch.py verify          # تمرین عملی هر ۵ مسیر (شبانه در CI)
python3 scripts/reaper.py --dry-run           # leaseهای زامبی
python3 -m unittest discover -s tests         # مجموعهٔ تست
python3 scripts/context_pack.py               # بازتولید CONTEXT-PACK.md
```

## ۵) ساختار و مالکیت

- منطق مشترک فقط در `scripts/lib/`؛ hookها و workflowها لایهٔ نازک روی آن‌اند. کپی منطق ممنوع.
- `receipts/`، `state/events/`، `state/locks/`، `state/budget/`، `state/a2a/` فقط از طریق script نوشته می‌شوند — ویرایش دستی = شکستن زنجیره.
- چهار مسیر مالک انسانی است (CODEOWNERS): `configs/pricing/**`, `**/ToS*`, `infra/terraform/**`, `security/iam/**`.
- هر agent بدون Agent Card معتبر (`agents/cards/`) فعال نمی‌شود.

## ۶) ایمنی

- kill switch پنج‌مسیره (§۶.۳): K1 `state/KILL` · K2 env `KILL_SWITCH` · K3 Moxt · K4 `scripts/killswitch.py` · K5 خودکار.
- غیرفعال‌سازی kill switch همیشه انسانی و با ADR.
- محتوای خارجی همیشه `untrusted` و با envelope مرزدار (`policy.wrap_untrusted`).
- hookها network I/O ندارند و در بودجهٔ زمانی ردهٔ خود (<3s / <90s) می‌مانند.

## ۷) سبک کد

- Python stdlib-only در `scripts/lib/` و `hooks/` (بدون وابستگی خارجی؛ `jsonschema` فقط lazy در strict mode).
- هیچ `datetime.now()`/`time.time()` خارج از `lib/clock.py` — `scripts/verify.py --lint-clock`.
- هیچ import چرخه‌ای در lib — `scripts/verify.py --lint-imports`.
- commit message انگلیسی، با task id (`T-…`).
- اسناد راهبردی فارسی، کد و schema انگلیسی.
