# TRADEOFF-REGISTER — ثبت زندهٔ معامله‌های آگاهانه (I8)

> «بدون trade-off» وجود ندارد. هدف: trade-off **آگاهانه، محدود، ثبت‌شده و قابل‌برگشت**.
> این جدول زنده است؛ هر تصمیم جدید با هزینهٔ پذیرفته‌شده اینجا می‌آید. حذف یک سطر فقط با ADR.

| # | انتخاب | منفعت | هزینهٔ پذیرفته‌شده | مهار | منبع |
| ---| ---| ---| ---| ---| --- |
| T1 | GitHub SSoT | اکوسیستم، Actions، audit رایگان | وابستگی به پلتفرم | mirror روزانه + cold clone + adapter | ADR-001 D2 |
| T2 | Transport سه‌لایه به‌جای Gateway اجباری | حذف SPOF، تحویل بدون زیرساخت | سه مسیر برای نگهداری | envelope مشترک · contract test یکسان · T3 اختیاری | ADR-001 D1 |
| T3 | T1 به‌عنوان baseline | صفر زیرساخت، audit ذاتی | latency ۳۰–۹۰ ثانیه | T2 برای مسیرهای حساس؛ T3 در VS-12 | ADR-001 D1 |
| T4 | Event sourcing | replay، تعارض کمتر | حجم و نیاز به compact | compact ساعتی + archive + upcaster | BUILD-SPEC §۳.۲ |
| T5 | اتوماسیون کامل | سرعت و هزینهٔ کمتر | blast radius خطا | autonomy levels + kill switch + rollback | BUILD-SPEC §۶ |
| T6 | Sequential testing | تصمیم سریع‌تر | پیچیدگی آماری | always-valid p-value + SRM + یک موتور مشترک | GAP G12 |
| T7 | Control Room بومی Moxt | حذف SaaS پرداختی از مسیر Governance | بدون داشبورد تحلیلی آماده | Mini App + Grafana در VS-10 | ADR-001 D3 |
| T8 | حذف total order (`seq` سراسری) | حذف ساختاری merge conflict و retry storm | استدلال دربارهٔ ترتیب سخت‌تر | ULID + causation + `actor_seq` + تست replay | ADR-001 D4 |
| T9 | fail-closed سراسری | «نمی‌دانم» هرگز «مجاز» نمی‌شود | توقف‌های کاذب در قطعی شبکه | پنج مسیر مستقل + پنجرهٔ ۱۵ دقیقه + verify شبانه | ADR-001 D5 |
| T10 | sim اجباری قبل از prod | اثبات صادقانه بدون ریسک کاربر | هزینهٔ ساخت پیش‌پرداخت (~یک اسلایس) | همان هزینه در VS-4..VS-11 بازیافت می‌شود | ADR-001 D6 |
| T11 | بازبین خصمانه (two-key = دو تبار) | کلید دوم واقعی در سازمان تک‌نفره | هزینهٔ توکن بیشتر به‌ازای هر تغییر بحرانی | فقط روی مسیرهای بحرانی | ADR-001 D7 |
| T12 | Receipt کامل §۳.۳ | قابل‌ممیزی بودن کامل | حجم JSON ~۲×؛ نوشتن دستی سخت‌تر | سازندهٔ receipt بیشتر فیلدها را استنتاج می‌کند | ADR-002 D12 |
| T13 | `chain_index` به‌جای مرتب‌سازی زمانی | زنجیره زیر ساعت مجازی/skew درست می‌ماند | یک فیلد حالت بیشتر که باید یکنوا بماند | head file + `verify --repair-head` | ADR-002 D13 |
| T14 | پارتیشن جدای sim/prod | جداسازی ساختاری دادهٔ شبیه‌سازی | خواندن «همهٔ رویدادها» دو مسیر می‌خواهد | پیش‌فرض `world="prod"` | ADR-002 D14 |
| T15 | K1 مرجع تنها خواندن | hook بدون شبکه، <3s | تأخیر انتشار ≤۱۵ دقیقه برای K3/K5 | با پنجرهٔ تازگی هم‌تراز؛ K4 محلی و فوری | ADR-002 D15 |
| T16 | منطق taint در `policy.py` (نه `taint.py`) | بدون تکرار منطق | انحراف از نام‌فایل §۲.۲ | alias عمومی؛ استخراج refactor مکانیکی است | ADR-002 D16.1 |
| T17 | `ledger.ndjson` به‌جای `ledger.json` | بدون read-modify-write زیر بار موازی | انحراف از §۲.۲ | همان انتظام event log | ADR-002 D16.2 |
| T18 | قیمت مدل تأییدنشده (`unverified`) | سیستم بودجه از روز اول کار می‌کند | `forecast()` تقریبی تا تأیید Owner | پرچم `unverified` + هشدار؛ اقدام O1 | ADR-002 D17 |
| T19 | رویداد hookها فقط روی deny (pre_tool/post_tool) | حجم event قابل‌کنترل در مسیر داغ | allowهای hook در event log نیست (در tool log هست) | بازبینی در VS-3 اگر audit ناقص ماند | ADR-003 D19 |
| T20 | Personalization | conversion بالاتر | ریسک privacy | first-party + consent + حداقل داده | BUILD-SPEC §۱۸ |
| T21 | چند مسیر پروتکل | تاب‌آوری | هزینه و نگهداری بیشتر | اولویت بر اساس SLO، حداکثر ۳ مسیر | BUILD-SPEC §۱۸ |
| T22 | Multi-agent | تخصص و موازی‌سازی | هزینهٔ توکن و هماهنگی | budget per agent + reservation + Context Efficiency KPI | BUILD-SPEC §۱۸ |
| T23 | نتیجهٔ T2 ابتدا روی پلتفرم، سپس آینه به repo | پنجرهٔ ناسازگاری کوتاه queued/completed | heartbeat + رویداد آینه + idem store | ADR-005 D34 |
| T24 | heartbeat در sim توسط بازیگر dispatcher تازه می‌شود | یک بازیگر با دو نقش | جداسازی در VS-4 اگر سناریو پیچیده شد | ADR-005 D33 |
