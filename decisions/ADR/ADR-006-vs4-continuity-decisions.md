# ADR-006 — اجرای بخش نخست VS-4: رقابت actor_seq، رجیستری ناهنجاری، dead-man switch، و تمرین cold restore

- **وضعیت:** Accepted
- **تاریخ:** 2026-07-30
- **تصمیم‌گیرنده:** momo (جلسهٔ S-135341) — طبق مجوز BUILD-SPEC §۰ و تفویض Owner («تصمیم‌های فنی را خودت بگیر و گزارش بده»)
- **ورودی:** BUILD-SPEC v2.0 §۳.۲/§۶.۳/§۱۱/§۱۶/§۱۷ · ADR-001..005 · GAP-REPORT-005 · RECOVERY.md
- **دامنه:** `scripts/lib/{events,paths,deadman}.py` · `scripts/{anomaly,coldrestore,verify,sim}.py` · `sim/{actors,chaos,report}.py` · `sim/scenarios/{event_seq_race,killswitch_unreadable,owner_absent}.yaml` · `analytics/schemas/event.schema.json` · `tests/{test_lib,test_sim}.py`

---

## D35 — تخصیص actor_seq زیر قفل انحصاری فایل (رفع ریشه‌ای برخورد qa-gate)

**زمینه.** در جریان VS-3 دو پردازش هم‌راستا (پردازش inbox فایل T1 و نظرسنج نتیجهٔ T2) هر دو watermark موجود qa-gate (=4) را خواندند و هر دو seq ۵ و ۶ را منتشر کردند. نتیجه: `duplicate_seq=[5,6]` در لاگ production که `verify --events` را قرمز کرد. مکانیزم قبلی «خواندن watermark → اسکن دیسک → +۱ → نوشتن» بدون هیچ قفلی اجرا می‌شد؛ read-modify-write روی دو فایل جدا ذاتاً race است. این یک باگ production واقعی است و طبق §۱۶.۱ باید هم ریشه‌ای رفع و هم سناریوی رگرسیون داشته شود.

**تصمیم.** کل read-scan-write در `_next_actor_seq` زیر `fcntl.flock` انحصاری روی `state/events/_watermarks.lock` اجرا می‌شود. هر فراخوان fd مستقل خودش را باز می‌کند تا کرنل هم threadهای یک پردازش و هم پردازش‌های جدا را سریالیزه کند. stdlib-only می‌ماند (fcntl بخشی از stdlib POSIX است؛ در غیر POSIX بدون قفل fallback با کامنت صریح). اسکن دیسک به‌جای `rows[-1]` از `max` همهٔ سطرها استفاده می‌کند تا در برابر بی‌نظمی تاریخی فایل هم شمارنده هرگز عقب نرود.

**رد شد.** *قفل در حافظهٔ پردازش (threading.Lock)* — پردازش‌های جدا را پوشش نمی‌دهد (دقیقاً سناریوی qa-gate). *صف پیام/سرویس خارجی* — نقض G9 (بدون شبکه در lib).

## D36 — رجیستری ناهنجاری با استناد ADR، به‌جای ویرایش لاگ یا تضعیف آشکارساز

**زمینه.** §۳.۲ صریح است: «هرگز edit، هرگز delete» — رویدادهای خام تغییرناپذیرند، پس خسارت تاریخی (seqهای تکراری) قابل حذف نیست. از سوی دیگر، گذرگاهی که به‌خاطر یک ناهنجاری *توضیح‌داده‌شده و رفع‌شده* هفت روز قرمز بماند، آموزش‌دهندهٔ نادیده‌گرفتن قرمز است — و «گيتی که خاموش شود بدتر از نبودن است» (§۱۴). تضعیف کور `detect_gaps` هم دقیقاً همان چیزی است که کامنت کد از آن هشدار می‌دهد.

**تصمیم.** `state/events/_anomalies.json`: رجیستری استثناهای توضیح‌یافته که فقط از طریق `events.register_anomaly()` / `scripts/anomaly.py` نوشته می‌شود (ویرایش دستی = همان جرم ویرایش لاگ). هر ورودی: actor، روز، نوع، seqها، event_idهای دقیق، **ارجاع اجباری به ADR**، ثبت‌کننده، و یک رویداد حسابرسی `event.anomaly.registered`. `detect_gaps(honor_registry=True)` (پیش‌فرض) seqهای ثبت‌شده را کم می‌کند و برای بقیه همان‌قدر سخت‌گیر می‌ماند؛ نمای خام forensics با `honor_registry=False` همیشه در دسترس است و `verify --events --json` هر دو را گزارش می‌کند.

**رد شد.** *بازنویسی seqها در لاگ* — نقض §۳.۲. *افزودن روزنهٔ کلی در آشکارساز* — آشکارسازی که دائمًا سوت‌کذب می‌کند خاموش می‌شود. *صبر تا کهنه‌شدن پنجرهٔ ۷روزه* — هفت روز گذرگاه قرمز = نرمال‌شدن قرمز.

## D37 — Dead-man switch به‌صورت دروازهٔ منتشرشده در lib/deadman.py

**زمینه.** §۱۱.۲: سکوت Owner بیش از ۷۲ ساعت ⇒ capabilityهای L1 به «queue + hold» و ادامهٔ L2/L3 (safe-continue)؛ بیش از ۱۴ روز ⇒ read-only. حضور انسان باید از روی لاگ استنباط شود، نه حافظه (همان فلسفهٔ §۱۱.۱ STEP 3).

**تصمیم.** `scripts/lib/deadman.py`: منحصر‌به‌فرد بودن پیاده‌سازی. `owner.heartbeat` در لاگ = حضور؛ `compute_level` سن سکوت را به سطح نگاشت می‌کند؛ enforceکننده (tick ارکستراتور در prod، DeadManSwitchActor در sim) با `refresh()` وضعیت را در `state/deadman.json` منتشر می‌کند و گذارها `deadman.engaged`/`deadman.escalated` منتشر می‌شوند. workerها با `allows(level)` فقط فایل منتشرشده را می‌خوانند (دقیقاً الگوی K1 برای kill switch). نکتهٔ کلیدی: **بدون فایل deadman.json دروازه وجود ندارد** — کتابخانه‌ای که در هر محیط بدون enforceکننده خودش را فعال کند، آشکارساز سوت‌کذب است. نبود هیچ heartbeat‌ای اما fail-closed به سخت‌گیرانه‌ترین سطح است («نمی‌دانم» = متوقف شو).

**رد شد.** *محاسبهٔ ad-hoc سطح در هر worker* — N بار اسکن لاگ در مسیر داغ + انحراف پیاده‌سازی‌ها از هم. *چک در policy engine برای این اسلایس* — یکپارچه‌سازی policy در VS-4 بعدی؛ اکنون دروازهٔ lib + سیم‌کشی actorها اثبات رفتار است.

## D38 — عدم جانشینی Owner در sim (replaceable=False)

**زمینه.** succession در harness هر بازیگر مرده را با standby زنده می‌کرد. برای سناریوی owner_absent این یعنی «رستاخیز انسان» — دقیقاً ناقض فرضیه‌ای که dead-man switch برایش ساخته شده: غیبت انسان یک واقعیت است، نه یک crash قابل‌ترمیم.

**تصمیم.** `ActorBase.replaceable = True` به‌عنوان پیش‌فرض؛ `OwnerActor.replaceable = False`؛ harness فقط بازیگران replaceable را جانشین می‌کند. سناریو با `successions_max: 0` اثبات می‌کند Owner احیا نشده.

**رد شد.** *حذف owner از ACTOR_REGISTRY و شبیه‌سازی با غایب‌بودن* — آنگاه «حضور قبل از غیبت» (مبنای ۷۲ ساعت سکوت) قابل‌بازی نبود.

## D39 — تمرین cold restore با راستی‌آزمایی دقیق compacted_from

**زمینه.** §۱۱.۲ معیار چهارگانه می‌خواهد و خروجی امتیازدار در `state/archive/drills/`. معیار ۱ («STATE بازسازی‌شده = اصلی به‌جز generated_at») یک ظرافت ساختاری دارد: compaction رویداد حسابرسی خودش (`state.compacted`) را *بعد از* نوشتن snapshot منتشر می‌کند، پس mirror همیشه یک رویداد بیشتر از چیزی دارد که snapshot اصلی شمرده است. برابری کور `event_count` همیشه fail می‌شود — نه به‌خاطر نقض، بلکه به‌خاطر هندسهٔ خودِ فرایند.

**تصمیم.** `scripts/coldrestore.py`: (۰) compaction پیش از تمرین روی root واقعی تا «اصلی» از همان مجموعهٔ رویداد mirror مشتق شده باشد؛ (۱) فیلدهای ساعتی (`generated_at`، `until_ts`، `read_at`/`freshness_s` مربوط به kill switch) در فهرست صریح و ممیزی‌شده نادیده گرفته می‌شوند؛ بلوک `compacted_from` به‌جای diff کور، **مستقیم برابر لاگ mirror** راستی‌آزمایی می‌شود (event_count با شمارش مستقل، watermarkها با delta دقیق: system-compact ≥ +1 و بقیه صفر)؛ (۲) `verify --chain` در mirror؛ (۳) همهٔ KPIهای موجود در STATE با تلرانس <۱٪ (CSR/NSM وقتی analytics در STATE منتشرشان کند خودکار وارد مقایسه می‌شوند)؛ (۴) task ساختگی end-to-end در mirror (lease → رویداد → receipt → پیشروی زنجیره → release). خروجی امتیازدار JSON در `state/archive/drills/` + رویداد `drill.cold_restore.completed`.

**رد شد.** *حذف compacted_from از مقایسه* — قوی‌ترین سیگنال بازتولیدپذیری را دور می‌ریخت. *مقایسه با STATE روزهای قبل* — انحراف واقعی lease/بودجه را به شکست تمرین ترجمه می‌کرد.

## D40 — بازاستفاده از `killswitch.unknown` برای رویداد «unreadable»

**زمینه.** §۶.۳ نام رویداد را `killswitch.unreadable` می‌گوید؛ taxonomy موجود (§۱۳.۱ «حداقل مجموعه») `killswitch.unknown` را دارد با همین معنا.

**تصمیم.** از `killswitch.unknown` استفاده می‌شود؛ افزودن نوع دوم برای یک معنا، taxonomy را دوپارچه می‌کرد. در سناریو، اولین verdict ناخوانا این رویداد را با detail و freshness منتشر می‌کند.

## D41 — سه سناریوی sim به‌عنوان سوییت رگرسیون VS-4

**زمینه.** §۱۶.۱: هر باگ production یک سناریو — بدون استثنا. §۱۷ برای VS-4: halt در ناخوانا + اثبات dead-man switch در sim. سناریوهای باقی‌ماندهٔ §۱۶ (۸ تا) به اسلایس‌های خودشان تعلق دارند.

**تصمیم.** (۱) `event_seq_race` — رگرسیون D35: طوفان ۱۶ thread × ۴۰ رویداد روی یک پارتیشن در یک لحظهٔ مجازی؛ انتظار `event_seq_duplicates == 0`. (۲) `killswitch_unreadable` — کهنه‌شدن heartbeat بعد از مرگ سرویس و standbyش ⇒ halt سطح L2 + رویداد + ازسرگیری با reconcile اپراتور؛ خرابی KILL ⇒ engaged. (۳) `owner_absent` — ۳۶۰ ساعت مجازی: اجرای L1 در حضور، queue شدن L1 بعد از ۷۲ ساعت، ادامهٔ L2 (مهار قطعی node در همان پنجره)، read-only بعد از ۱۴ روز (عدم مهار قطعی دوم). هر سه روی ۳ seed با score ۱٫۰.

**رد شد.** *پوشش هر ۵ مسیر kill switch در یک سناریوی واحد* — تمرین عملی زندهٔ هر ۵ مسیر را `killswitch.py verify` (۱۰/۱۰ در CI شبانه) انجام می‌دهد؛ سناریو مکمل است نه جایگزین.

## D42 — اشتقاق فیلدهای حمل‌شدهٔ STATE از رویدادها (یافتهٔ خود تمرین cold restore)

**زمینه.** اولین اجرای تمرین cold restore معیار ۱ را با ۷ اختلاف واقعی fail کرد — دقیقاً کاری که برایش ساخته شده بود: `phase`/`active_slice` فقط در bootstrap نوشته می‌شدند، `owner_agent` فقط در claim، و `health=red` فقط در reaper؛ compaction همه را از STATE قبلی merge-forward می‌کرد و بازسازی از صفر (state.empty) آن‌ها را به پیش‌فرض برمی‌گرداند. ادعای §۳.۱ («STATE از event log بازسازی می‌شود») برای این چهار فیلد دروغ بود.

**تصمیم.** compact.py حالا این فیلدها را از جریان رویداد (مرتب‌شده بر اساس ts) اشتقاق می‌کند: `session.started` با payload.phase/slice ⇒ فاز و اسلایس · `lease.acquired` ⇒ owner_agent + health=unknown (lease زنده بر تصادف گذشته غلبه می‌کند) · `task.crashed`/`lease.revoked` ⇒ health=red. قاعده: جدیدترین رویداد در پنجره پیروز است؛ فیلدی که در این پنجره رویدادی ندارد مقدار حمل‌شده را نگه می‌دارد. هر دو مسیر (از صفر و merge) به یک نتیجه می‌رسند — تعریفِ «مشتق».

**رد شد.** *پرسیدن از کاربر دربارهٔ مقادیر درست هنگام restore* — نقض همان اصل «به حافظه اعتماد نکن» (§۱۱.۱ STEP 3). *قرار دادن health در receipt* — health یک نمای زندهٔ workstream است، نه خاصیت یک task.
