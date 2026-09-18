# ADR-015 — استقرار ۷ ایجنت کلیدی Tier 0، نگهبان تداوم، و بازبین متخاصم مستقل (VS-5)

- **وضعیت:** Accepted
- **تاریخ:** 2026-09-18
- **تصمیم‌گیرنده:** momo (جلسهٔ S-142302) — بر اساس الزامات صریح BUILD-SPEC v2.0 §3.4, §10.1, §11.1
- **ورودی:** BUILD-SPEC v2.0 §3.4, §10, §11 · ADR-001, ADR-005, ADR-006, ADR-014 · `analytics/schemas/agent-card.schema.json`
- **دامنه:** `agents/cards/*.yaml` · `scripts/lib/{handoff_guardian,adversarial_reviewer,events}.py` · `scripts/{handoff,review}.py` · `analytics/schemas/event.schema.json` · `tests/test_tier0_agents.py` · `state/HEALTH-BASELINE.json`

---

## D56 — استقرار ۷ کارت ایجنت کلیدی Tier 0 در agents/cards/

**زمینه.** طبق صریح BUILD-SPEC §10.1، هیچ ایجنتی بدون Agent Card معتبر فعال نمی‌شود. همچنین ترتیب ساخت اجباری است: ابتدا ۷ ایجنت Tier 0 (کامل و سبز) باید پیاده شوند. هر کارت باید اسکیما (`analytics/schemas/agent-card.schema.json`) را رعایت کند و قوانین بین-کارتی (عدم همپوشانی `owns`، متریک متقابل با مالک متفاوت I13، سناریوهای الزامی شبیه‌ساز، و کلاس یکتای idempotency برای هر قابلیت جهش‌یافته) را برآورده سازد.

**تصمیم.** ایجاد ۷ کارت YAML در `agents/cards/`:
1. `orchestrator.yaml`: ارکستراتور کلان (L2/L3)، مالک مسیرهای routing و قفل‌ها، هدایت رویدادها، با Counter-KPI تحت مالکیت `adversarial-reviewer`.
2. `config-engineer.yaml`: مهندس کانفیگ (L2)، مالک `configs/**` با Counter-KPI نرخ رول‌بک تحت مالکیت `qa-gate`.
3. `infra-sre.yaml`: مهندس زیرساخت و پایداری (L1)، مالک `infra/**` با Counter-KPI نرخ شکست تغییر تحت مالکیت `security-compliance`.
4. `qa-gate.yaml`: دروازهٔ کیفیت (L2/L3)، مالک تست‌ها و آرتیفکت‌های QA با Counter-KPI پاس‌کاذب تحت مالکیت `adversarial-reviewer`.
5. `security-compliance.yaml`: امنیت و انطباق (L1)، مالک `security/**` با الزامات Four-Eyes.
6. `handoff-guardian.yaml`: نگهبان تداوم (L2/L3)، مالک `state/HANDOFF.md` و تولید شاخص تداوم عملیات.
7. `adversarial-reviewer.yaml`: بازبین متخاصم با تبار مستقل (`gpt-4o/adversarial@1`)، بدون مالکیت مسیر، با اختیارات L3 برای رد و L0 برای تأیید.

**رد شد.** *تعریف ایجنت‌ها صرفاً در رجیستری JSON ساده* — ناکافی برای الزام‌های بودجه، SLA ضربان قلب، و متریک‌های متقابل.

---

## D57 — موتور نگهبان تداوم (Handoff Guardian) و شاخص پیوستگی عملیاتی (continuity_score)

**زمینه.** طبق قانون آهنین ۳ و §10.1، هیچ جلسه‌ای بدون HANDOFF بسته نمی‌شود و سیستم باید بتواند شاخص پیوستگی عملیاتی بین سشن‌ها را بسنجد.

**تصمیم.** پیاده‌سازی `scripts/lib/handoff_guardian.py` و واسط کاربری خط فرمان `scripts/handoff.py`:
- تابع `verify_handoff()`: ساختار، تاریخ، نشست و سرفصل‌های الزامی `state/HANDOFF.md` را اعتبارسنجی می‌کند.
- تابع `compute_continuity_score()`: ۴ مؤلفهٔ کلیدی را ارزیابی کرده و نمره نهایی بین 0.0 تا 1.0 را محاسبه می‌کند:
  1. تازگی و اعتبار HANDOFF.md (وزن ۰.۲۵)
  2. پوشش صددرصدی رسیدها (وزن ۰.۲۵)
  3. عدم وجود قفل زامبی بلاتکلیف (وزن ۰.۲۵)
  4. سلامت خط پایه پروژه در HEALTH-BASELINE.json (وزن ۰.۲۵)
- صدور رویداد حسابرسی `continuity.scored` در لاگ رویدادها.

**رد شد.** *سنجش تداوم صرفاً بر اساس وجود فیزیکی فایل بدون بررسی جامع سلامت زنجیره و قفل‌ها*.

---

## D58 — بازبین متخاصم مستقل (Adversarial Reviewer) و ممانعت از خود-تأییدی

**زمینه.** طبق اصل Separation of Duties (§10)، هیچ ایجنتی حق ندارد خروجی خود را تأیید کند. همچنین بازبینی تغییرات حساس روی گیت‌های امنیتی و خطوط بحرانی نیازمند تباری کاملاً مستقل از ایجنت کدنویس است.

**تصمیم.** پیاده‌سازی `scripts/lib/adversarial_reviewer.py` و ابزار CLI `scripts/review.py`:
- انتساب تبار مستقل `gpt-4o/adversarial@1` به این نقش جهت جلوگیری از تبانی مدل‌ها (Lineage Collusion).
- رد خودکار هرگونه درخواست خود-بازبینی (`author == reviewer`).
- رد خودکار هرگونه تضعیف گیت‌های اعتبارسنجی روی مسیرهای بحرانی (`scripts/verify.py`، `scripts/lib/policy.py`، و غیره) یا دستکاری متریک‌ها بدون گاردریل متقابل.
- انتشار رویدادهای `review.rejected` و `review.approved` روی لاگ تغییرناپذیر سیستم.

---

## D59 — ارتقای خط پایه سلامت به ۲۲۶ تست (Health Baseline Update)

**زمینه.** با افزوده شدن مجموعه تست‌های اعتبارسنجی ایجنت‌های Tier 0 در `tests/test_tier0_agents.py`، کف قبلی ارتقا یافته است.

**تصمیم.** ثبت خط پایه جدید در `state/HEALTH-BASELINE.json`:
- تست‌ها: ۲۲۶/۲۲۶ پاس
- راستی‌آزمایی (verify): ۶/۶ پاس
- سناریوهای شبیه‌ساز: ۵۱/۵۱ پاس
- دریل بازیابی سرد: ۱/۱ با امتیاز ۱.۰
