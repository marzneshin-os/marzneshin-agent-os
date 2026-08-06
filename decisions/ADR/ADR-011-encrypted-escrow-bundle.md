# ADR-011 — بستهٔ escrowِ رمزنگاری‌شده: رمزنگاری واقعی، بدون secret در مخزن، drift = شکست

- **وضعیت:** Accepted
- **تاریخ:** 2026-08-04
- **تصمیم‌گیرنده:** momo (جلسهٔ S-120244) — طبق مجوز BUILD-SPEC §۰ و تفویض صریح Owner
- **ورودی:** BUILD-SPEC v2.0 §۱۱.۲ («بستهٔ رمزنگاری‌شده در mirror روزانه بازتولید می‌شود») · I6 · I12 · قانون آهنین ۴ · `state/HANDOFF.md` (نخستین آیتم باز)
- **دامنه:** `scripts/escrow.py` · `.github/workflows/mirror.yml` · `scripts/lib/events.py` · `analytics/schemas/event.schema.json` · `tests/test_scripts.py`

---

## D50 — رمزنگاری با openssl و passphrase فقط از env؛ نبود passphrase یعنی هیچ بسته‌ای

**زمینه.** گام escrow در `mirror.yml` یک `tar czf` ساده بود با `2>/dev/null || true` — یعنی هم رمزنگاری نبود (نقض صریح §۱۱.۲) و هم fail-open: اگر چیزی می‌شکست، گام سبز می‌ماند. بستهٔ escrow نقشهٔ کامل «چطور سیستم را متوقف/باطل کنی» است؛ نسخهٔ متن‌بازِ آن خودش یک artifact حساس است — بدتر از نبودنش.

**تصمیم.** `scripts/escrow.py build` بسته را با `openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt` رمز می‌کند. passphrase فقط از `MARZ_ESCROW_PASSPHRASE` خوانده می‌شود و با `-pass env:` به openssl داده می‌شود تا در argv/ps نیفتد (I6، قانون ۴). اگر passphrase یا openssl نباشد: خروج با کد ۲ و **هیچ فایلی نوشته نمی‌شود** — fail-closed، نه «بساز و هشدار بده». محتوا طبق §۱۱.۲: RECOVERY.md (مسیرهای kill switch به زبان ساده) + `ACCESS-INVENTORY.json` ماشین‌ساز (agents از registry، مسیرهای انسانی از CODEOWNERS، workflowها) تا از رجیستری عقب نماند + BUILD-SPEC/CODEOWNERS/CLAUDE.md/decisions + `manifest.json` با sha256 هر فایل.

**رد شد.** *وابستگی `cryptography` پایتون* — scripts/lib باید stdlib-only بماند (G9) و bootstrap جلسه (pyyaml + jsonschema) برای یک ابزارِ مسیرِ ایمنی سنگین‌تر نمی‌شود؛ openssl روی هر runnerای هست. *`age`/`gpg`* — کمتر همه‌جا حاضر. *tar ساده + هشدار در کامنت* — همان چیزی که این ADR وجود دارد تا ببندد.

## D51 — verify گردش کامل است و drift را شکست می‌داند، نه هشدار

**زمینه.** بسته‌ای که نتوان آن را باز کرد یا محتوایش را سنجید، escrow نیست — دکور است. و بسته‌ای که RECOVERY.mdِ دیروز را دارد، راهنمای نجاتِ سیستمِ امروز نیست.

**تصمیم.** `escrow.py verify <bundle>`: رمزگشایی (passphrase غلط = خروج ۲) → سنجش sha256 هر فایل با manifest (ناسازگاری = خروج ۱) → **سنجش drift**: اگر RECOVERY.md داخل بسته با نسخهٔ فعلی مخزن فرق کند، بسته کهنه است و verify قرمز می‌شود (خروج ۱). رویدادهای `escrow.built`/`escrow.verified` در **همان commit** به واژگان اضافه شدند (قاعدهٔ ADR-008). گام escrow در `mirror.yml` حالا `build` و بلافاصله `verify` را صدا می‌زند و `|| true` حذف شد: نبودِ secretِ `ESCROW_PASSPHRASE` گام را قرمز می‌کند — این قرمز، درخواستِ صریحِ اقدام از Owner است (O5)، نه صدای اضافه.

**رد شد.** *verify فقط در CI* — قرارداد باید روی هر کلون قابل اجرا باشد، وگرنه drillِ §۱۱.۲ نمی‌تواند آن را مصرف کند. *drift به‌عنوان warning* — «هشداری که کسی نمی‌بیند» همان کلاس نقصی است که ADR-007 برای گذرگاه‌ها ثبت کرد. *کامیت‌کردن بستهٔ روزانه در مخزن* — رشد بی‌رویهٔ history برای artifactی که artifactِ workflow با retention ۳۰ روزه هست.

**اعتبارسنجی.** چهار تست CLI روی ریشهٔ دورانداختنی: گردش build→verify سبز · بدون passphrase هیچ فایلی ساخته نمی‌شود و کد ۲ · تغییر RECOVERY.md پس از build ⇒ verify قرمز با پیام drift · passphrase غلط ⇒ شکست رمزگشایی. اول هر چهار قرمز (اسکریپت وجود نداشت)، بعد سبز — ترتیب I11.
