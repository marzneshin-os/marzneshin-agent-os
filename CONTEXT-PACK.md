# [TIER-0: IMMUTABLE OS GOVERNANCE]

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
python3 scripts/webcmd_cli.py status       # بررسی وضعیت و صرفه‌جویی توکن مرورگر WebCMD
python3 scripts/webcmd_cli.py browse <url> # وب‌گردی بهینه‌شده با کاهش ۹۰ درصدی توکن
python3 scripts/ecc_cli.py status          # بررسی وضعیت هماهنگی ECC و پلتفرم‌ها
python3 scripts/ecc_cli.py scan            # اسکن امنیتی AgentShield
python3 scripts/ecc_cli.py instincts       # غرایز یادگیری و قوانین کشف‌شده
python3 scripts/worktree_cli.py list       # مدیریت موازی‌سازی Git Worktrees (الگوی بوریس چرنی)
python3 scripts/antigravity_doctor_cli.py diagnose # دیاگنوستیک کامل سلامت محیط و MCPها
python3 scripts/reason_cli.py status          # وضعیت شبکه مش P2P و ایجنت‌های متصل (Reason Network)
python3 scripts/reason_cli.py who             # لیست ایجنت‌های آنلاین همکار در شبکه (ADR-030)
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

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


## ۸) دستورهای اسلش اختصاصی Claude Code (`.claude/commands/`)
- `/verify`: اجرای تست ۶ مرحله‌ای تاییدیه دوکلیدی (`python3 scripts/verify.py --all`)
- `/fsp-start`: بررسی وضعیت و تصاحب ورک‌استریم با توکن fencing
- `/plan`: فعال‌سازی حالت تفکر و تحلیل بدون جهش به کدنویسی (Karpathy Guidelines)
- `/sim`: شبیه‌سازی سناریوها در `sim/` قبل از انتشار کانفیگ
- `/qa-gate`: ارزیابی رسید و بررسی وضعیت rollback
- `/handoff`: بازنویسی `state/HANDOFF.md` و آزادسازی لیس‌ها
- `/worktree`: مدیریت موازی‌سازی ترمینال‌ها با Git Worktrees (الگوی بوریس چرنی)
- `/doctor`: عیب‌یابی سلامت MCPها و حساب‌ها
- `/killswitch`: پایش وضعیت یا همگام‌سازی K1-K5
- `/setup`: اسکن پروژه و پیشنهاد اتوماسیون‌های هوشمند مطابق استاندارد رسمی `claude-code-setup` آنتروپیک
- `/cost`: پایش هزینه دلاری و توکن‌های مصرفی سشن و تطبیق با سقف بودجه
- `/reason`: پایش و اتصال به شبکه مش P2P ایجنت‌های محلی (Reason Network)

## FreeLLMAPI Universal Free-Tier Token Pool (~7.4B Tokens/Month)
- **Local Gateway**: `http://127.0.0.1:3001/v1` (OpenAI & Anthropic `/v1/messages` compatible)
- **Status & Diagnostics**: `python3 scripts/freellm_cli.py status`
- **Catalog of Free Models**: `python3 scripts/freellm_cli.py catalog --domain coding`
- **Failover**: Auto-switches across 34+ free-tier providers on 429 rate limit with multi-key cooldown.

## ۹) بودجه، پایش هزینه و سقف مصرف (Cost Tracking & Budget Governance)

> **شعار حاکم:** «Count it, cap it, then scale it» — پیش از افزودن ساب‌ایجنت‌ها، سقف قیمت‌گذاری و تلمتری دقیق الزامی است.

### سقف بودجه مصوب به ازای هر تسک و مرحله:
- **سقف کل هر تسک (Hard Stop):** حداکثر **۲.۰۰ دلار** (سقف ~۶۰۰,۰۰۰ توکن).
- **تفکیک مراحل چرخه (Stage Budget Limits):**
  - **Ingest / Sync** (`SYNC`, `GAP SCAN`, `CLAIM`): **$0.10**
  - **Plan** (`PLAN`, `ADR`): **$0.25**
  - **Execute** (`SIM`, `EXECUTE`): **$1.00**
  - **Verify** (`VERIFY`, شبیه‌سازی و تست‌ها): **$0.35**
  - **Gate** (`EMIT`, Two-Key Sign-off): **$0.15**
  - **Commit / Handoff** (`HANDOFF`, انتشار Claim): **$0.15**

### قوانین آهنین بودجه:
1. **توقف خودکار (Hard Stop):** به محض عبور هزینه هر مرحله از سقف دلاری خود یا رسیدن به ۸۰٪ سقف کلی تسک، عامل **موظف است فوراً متوقف شود** و با اجرای `/cost` از کاربر تاییدیه بخواهد.
2. **پایش مداوم در نوار وضعیت (Status Line):** هزینه دلاری سشن و توکن‌های مصرفی پیوسته در وضعیت ترمینال چاپ می‌شود.
3. **لاگ الزامی دست‌به‌دست شدن عامل‌ها (Handoff Log):** هوک `SubagentStop` در هر بار پایان کار ساب‌ایجنت، نام عامل، تسک محوله و مصرف توکن را در `logs/handoffs.log` ثبت می‌کند.
4. **سقف صریح دور ساب‌ایجنت‌ها (Turn Limits):** هر ساب‌ایجنت در `.claude/agents/` دارای `maxTurns` بین ۸ تا ۱۲ دور است؛ هیچ عاملی حق چرخش نامحدود ندارد.
5. **بررسی الزامی پیش از تغییر مرحله:** قبل از شروع مرحله بعدی، بررسی هزینه با دستور اسلش `/cost` انجام می‌پذیرد.

## ۱۰) افزونه رسمی آنتروپیک (`claude-code-setup`) و استاندارد اتوماسیون (ADR-031)

- **نصب افزونه رسمی از مارکت‌پلیس آنتروپیک:**
  ```bash
  /plugin install claude-code-setup@claude-plugins-official
  ```
- **دستور اسکن پروژه و پیشنهاد اتوماسیون:** اجرای دستور میان‌بر `/setup` در خط فرمان Claude Code.
- **هوک‌های حفاظتی و اعلان‌ها (Hooks Layer):**
  - `hooks/pre_tool.py`: جلوگیری فعال از تغییر ناخواسته فایل‌های `.env*`, `package-lock.json`, `poetry.lock` و کلیدها.
  - `hooks/notification.py`: زنگ اعلان ترمینال و لاگ رویدادها در `logs/notifications.log` برای `permission_prompt` و `idle_prompt`.
- **مستندات زنده کتابخانه‌ها (MCP Layer):**
  - اتصال به سرور `context7` (`@upstash/context7-mcp`) در `.mcp.json` برای ارجاع بی‌درنگ به مستندات به‌روز پکیج‌ها و جلوگیری از توهم متدهای API.
- **مهارت‌های پس‌زمینه و کمکی (Skills Layer):**
  - `project-conventions`: مهارت اختصاصی پس‌زمینه (`user-invocable: false`) برای اعمال خودکار قواعد مخزن (Stdlib-only در lib، ساعت مجازی، Zero Circular Import و Two-Key verification).
  - `gen-test`: مهارت اختصاصی تولید تست‌های استاندارد با ساختار `unittest.TestCase`.

## ۱۱) پشته طلایی ابزارهای هوش مصنوعی ۲۰۲۶ (استاندارد خیرالله العوضی - ADR-032)

> بر اساس مرجع ۲۰۲۶ مهندس خیرالله العوضی (@eng_khairallah1):
> **پشته طلایی توسعه‌دهندگان:** Claude Code (01) + Superpowers (05) + Context7 (17) + Tavily (16)

### ارکان پیکربندی‌شده در پروژه:
1. **جستجو و خزش تمیز وب (Tavily AI Search - ابزار ۱۶):**
   - اتصال سرور MCP بومی پایتون scripts/mcp_tavily.py با ابزارهای 	avily_search, 	avily_extract, 	avily_crawl, 	avily_map.
   - فیل‌اور خودکار به موتور وبگردی بهینه webcmd در صورت عدم تنظیم کلید API.
2. **مدیریت تسک‌های ساختاریافته (Task Master AI - ابزار ۱۸):**
   - اسکریپت scripts/taskmaster_cli.py جهت تبدیل PRD به پایپ‌لاین گراف تسک‌ها در state/tasks.json با دستور /taskmaster.
3. **توسعه مبتنی بر مشخصات (Spec Kit SDD - ابزار ۰۶):**
   - مهارت spec-kit و دستور /spec برای تدوین مشخصه قبل از هرگونه کدنویسی.
4. **مهندسی کانتکست و پایداری KV-Cache (ابزار ۲۹):**
   - مهارت context-engineering با استراتژی پیشوند پایدار (Stable Prefixes)، ماسک کردن خروجی‌های سنگین و افشای تدریجی (Progressive Disclosure) جهت کاهش ۹۰ درصدی هزینه کش آنتروپیک.
5. **پژوهش عمیق و راستی‌آزمایی (Deep Research - ابزار ۳۰):**
   - مهارت و دستور /deep-research با فرآیند ۸ مرحله‌ای و اعتبارسنجی چندمنبعی.
6. **تولید خودکار مهارت و طراحی رابط کاربری (ابزارهای ۲۴ و ۲۵ آنتروپیک):**
   - مهارت‌های رسمی skill-creator (دستور /new-skill) و rontend-design.

## ۱۲) زرادخانه ابزارهای مهندسی هوش مصنوعی ۲۰۲۶ (Deep-Dive Extension - ADR-033)

> تکمیلی مرجع ۲۰۲۶ مهندس خیرالله العوضی (@eng_khairallah1):
> ادغام عمیق قابلیت‌های پیشرفته مرورگر، توسعه ابزارها، اعتبارسنجی خروجی، هوش اسناد و مانیتورینگ گیت‌وی.

### قابلیت‌های پیشرفته پیاده‌سازی‌شده:
1. **اتوماسیون مرورگر و تست E2E (Playwright MCP - ابزار ۱۹):**
   - اتصال سرور رسمی @playwright/mcp@latest به .mcp.json جهت تعامل با داشبوردها، کلیک، پر کردن فرم‌ها و ثبت اسکرین‌شات با دستور /playwright.
2. **چارچوب توسعه سریع FastMCP (ابزار ۲۰):**
   - ماژول scripts/lib/fastmcp_harness.py جهت ساخت ابزارهای MCP پایتون بر پایه دکوراتور @mcp.tool() و تولید خودکار JSON Schema با دستور /fastmcp.
3. **موتور خروجی ساختاریافته Instructor و Pydantic-AI (ابزارهای ۱۵ و ۴۴):**
   - ماژول scripts/lib/structured_output.py برای اعتبارسنجی ۱۰۰ درصدی داده‌ها بر اساس شِماهای nalytics/schemas/ و تلاش مجدد خودکار با دستور /structured.
4. **هوش اسناد و پردازش PDF و Markdownify (ابزارهای ۲۱ و ۲۳):**
   - مهارت رسمی pdf آنتروپیک و اسکریپت scripts/markdownify_cli.py جهت تبدیل اسناد، جداول و فایل‌های مرجع (نظیر FreeLLMAPI_Guide.pdf) به مارک‌داون تمیز با دستورات /pdf و /markdownify.
5. **کاوشگر دیتابیس و زبان طبیعی به SQL (ابزار ۴۳ Vanna AI / NL-SQL):**
   - ابزار scripts/db_query_cli.py جهت بازرسی امن، سریع و Read-Only چک‌پوینت‌های ۵۰۰+ تایی LangGraph و جداول دیتابیس با دستور /db-query.
6. **تاب‌آوری و کنترل گیت‌وی Portkey و OmniRoute (ابزارهای ۴۹ و ۵۰):**
   - ماژول scripts/router_cli.py جهت بررسی وضعیت اتصال، سهمیه‌ها و زنجیره فیل‌اور میان گیت‌وی‌های OmniRoute، CCR و FreeLLM pool با دستور /router.
7. **داشبورد سلامت متمرکز MCPHub (ابزار ۲۲):**
   - ابزار scripts/mcphub_cli.py جهت پایش بلادرنگ سلامت، زمان تاخیر (Latency) و شمارش ابزارهای هر ۱۳ سرور MCP متصل به سیستم با دستور /mcphub.
8. **گراف دانش کدبیس Graphify (ابزار ۵۲ Codebase Memory):**
   - دستور مستقیم /graphify در خط فرمان Claude Code برای بررسی God Nodes، نودهای مرتبط و محاسبه شعاع تخریب (Blast Radius) پیش از تغییرات بزرگ.

## The session protocol (BUILD-SPEC §0)

1. SYNC — `scripts/fsp.py status` + HANDOFF.md + recent receipts + kill switch
2. GAP SCAN — distance to the current slice's Definition of Done (§17)
3. CLAIM — `scripts/fsp.py claim <workstream> --agent <id>` (TTL 90m)
4. PLAN — at most 7 steps, each with a named artifact
5. SIM — run the related sim/ scenario first; red means no production
6. EXECUTE — real code, never placeholders
7. VERIFY — run tests, report real output
8. EMIT — event + receipt (with prev_receipt_hash) + atomic commit
9. HANDOFF — rewrite HANDOFF.md, release the lease

## Iron rules

1. No config reaches users without QA.  2. No campaign without hypothesis and stop condition.  3. No session ends without a HANDOFF.  4. No secret enters the repo.  5. No decision without owner, evidence and rollback.  6. "I don't know" equals "stop" — an unreadable safety control is engaged, not clear.

## Tradeoff Register
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

# [TIER-1: AGENT CARDS & CAPABILITIES]

# [TIER-2: APPROVED ADRs]
- `ADR-001-foundational-architecture.md`: # ADR-001 — تصمیم‌های بنیادی معماری
- `ADR-002-schema-alignment-and-deviations.md`: # ADR-002 — هم‌ترازی schema با BUILD-SPEC v2.0 و ثبت انحراف‌های عمدی
- `ADR-003-vs1-execution-decisions.md`: # ADR-003 — اجرای اسلایس VS-1: hookها، CI، و پل shibeh-sazi پیش از VS-2
- `ADR-004-vs2-closeout-decisions.md`: # ADR-004 — بستن اسلایس VS-2: انطباق ساعت، fixture قرارداد vault، و ترتیب sys.path تست
- `ADR-005-vs3-a2a-decisions.md`: # ADR-005 — اجرای اسلایس VS-3: گذرگاه A2A روی T1/T2، مسیریابی با fallback، و قراردادهای وابسته
- `ADR-006-vs4-continuity-decisions.md`: # ADR-006 — اجرای بخش نخست VS-4: رقابت actor_seq، رجیستری ناهنجاری، dead-man switch، و تمرین cold restore
- `ADR-007-crash-rate-window-and-tested-in-gate.md`: # ADR-007 — پنجرهٔ اندازه‌گیری crash_rate، و گذرگاه استاتیک برای `rollback.tested_in`
- `ADR-008-slice-transition-event.md`: # ADR-008 — رویداد `slice.transitioned`: اشارهگر فاز/اسلایس روی لاگ، نه با ویرایش دستی
- `ADR-009-save-baseline-never-narrows-floor.md`: # ADR-009 — `--save-baseline` هرگز کف را باریک نمی‌کند؛ ردِ ذخیره به‌جای حذفِ بی‌صدای گیت
- `ADR-010-executable-succession-flow.md`: # ADR-010 — گردش‌کار جانشینی §11.1 به‌صورت اجرایی: یک جریان در lib، دو محرک نازک
- `ADR-011-encrypted-escrow-bundle.md`: # ADR-011 — بستهٔ escrowِ رمزنگاری‌شده: رمزنگاری واقعی، بدون secret در مخزن، drift = شکست
- `ADR-012-llm-gateway-integration.md`: # ADR-012: LLM Gateway Integration (OmniRoute / 9Router)
- `ADR-013-claude-code-router-integration.md`: # ADR-013: Claude Code Router (CCR) Full Integration
- `ADR-014-vs4-closeout-sim-scenarios-succession-coldrestore.md`: # ADR-014 — تکمیل و بستن برش عمودی ۴ (VS-4): زمان‌بندی دریل بازیابی سرد، تکمیل سناریوهای §۱۶، و سیم‌کشی تولیدی جانشینی
- `ADR-015-vs5-tier0-agents-handoff-guardian-adversarial-reviewer.md`: # ADR-015 — استقرار ۷ ایجنت کلیدی Tier 0، نگهبان تداوم، و بازبین متخاصم مستقل (VS-5)
- `ADR-016-vs6-control-room-integration-moxt-reverse-sync.md`: # ADR-016 — یکپارچه‌سازی اتاق کنترل با ادپتر Moxt، همگام‌سازی ۵ جریان کاری، و استثناهای مجاز (VS-6)
- `ADR-017-vs7-config-canary-pipeline-auto-rollback.md`: # ADR-017 — پایپ‌لاین کانفیگ قناری، گیتینگ آماری، ناوگان پروب و بازگشت خودکار (VS-7)
- `ADR-018-vs8-growth-spine-taxonomy-nsm-upcasters.md`: # ADR-018 — ستون رشد، آپ‌کستر اسکیما، متریک ستاره قطبی و اقتصاد واحد (VS-8)
- `ADR-019-vs9-safe-experimentation-srm-guardrails-negative-results.md`: # ADR-019: Safe Experimentation, SRM Gates, Guardrail Auto-Stop, and Negative Results (VS-9)
- `ADR-020-vs10-revenue-command-center-unit-economics-counter-kpi-guardrails.md`: # ADR-020: Revenue Command Center, Live Token Costs in Unit Economics, and Counter-KPI Guardrails (VS-10)
- `ADR-021-vs11-autonomy-ratchet-shadow-mode-72h-autonomous-marathon.md`: # ADR-021: Autonomy Ratchet, Shadow Mode Agreement, and 72-Hour Autonomous Marathon (VS-11)
- `ADR-022-vs12-http-gateway-production-hardening-live-readiness.md`: # ADR-022: HTTP Gateway (VS-12), Production Hardening, and Full Autonomous Operating System Completion
- `ADR-023-cross-agentic-webcmd-browser-memory.md`: # ADR-023: Cross-Agentic WebCMD Self-Learning Browser Memory & Token Optimization Infrastructure
- `ADR-024-ecc-agent-harness-agentshield-continuous-learning.md`: # ADR-024: Everything Claude Code (ECC) Universal Agent Harness, AgentShield Security Auditor & Continuous Learning Architecture
- `ADR-025-antigravity-account-doctor-health-recovery.md`: # ADR-025: Antigravity Account Doctor, Health Recovery & Eligibility Remediation Architecture
- `ADR-026-grounded-notebook-knowledge-engine.md`: # ADR-026: Grounded Notebook Knowledge Engine (Synthesizing NotebookLM and Antigravity Paradigms)
- `ADR-027-system-one-typed-decisions-laya-jev-stacking.md`: # ADR-027: System 1 Typed Decisions & Jev+Claude Stacking Engine
- `ADR-028-three-tier-harness-loop-graph-architecture.md`: # ADR-028: Three-Tier Harness-Loop-Graph Architecture & Graph-and-Loop Engineering Engine
- `ADR-029-aws-bedrock-credit-pool-zero-cost-guardrail.md`: # ADR-029: AWS Bedrock Promotional Credit Pool & Zero-Cost Guardrail Engine Architecture
- `ADR-030-deterministic-prompt-prefix-stratification-kv-cache.md`: # ADR-030: Deterministic Prompt Prefix Stratification & KV-Cache Reuse Engine
- `ADR-034-antigravity-harness2-argon-reasoning.md`: # ADR-034: Antigravity IDE Harness 2.0 & Argon-Grade Deep Reasoning Integration

<!-- MARZNESHIN_KV_CACHE_BREAKPOINT_V1 -->

# [TIER-3: DYNAMIC SESSION TAIL — DO NOT CACHE]
## Safety & Live Controls
- Kill switch: **running** (all sources clear)
- Receipt chain: 34 receipts · crash_rate 17.65% (budget 2%)
- Active slice: **VS-12** — (optional) HTTP Gateway — latency cache only

## State Snapshot
```
phase=P1-agentic-core slice=VS-12 sense=Tick-D
snapshot_age=13s from 1823 events
kill_switch=running global=False
  agentic-core: health=unknown lease=free open=0 blocked=0
  main: health=unknown lease=free open=0 blocked=0
  kpis: crash_rate=0.1765, crash_rate_lifetime=0.1765, crash_rate_sample_sufficient=False, crash_rate_window=34, receipt_coverage=1.0, receipts_total=34
```

## Receipt chains
  - agentic-core: 34 receipts, head `sha256:54da13741a2…`

- **Active State Snapshot (`state/STATE.json`)**:
```json
{
  "active_slice": "VS-12",
  "budget": {
    "day": "2026-11-11",
    "forecast": {
      "tokens": 4811,
      "usd": 0.0112
    },
    "state": "normal",
    "tokens_spent_today": 2400,
    "usd_spent_today": 0.0056,
    "utilization": 0.0006
  },
  "canary": {
    "active_experiments": 0
  },
  "compacted_event_hash": "sha256:6536d221c163b0bacb65d15ae7eeb90fe19aa1c3dd0326638501b8d939eb4fd6",
  "compacted_from": {
    "actor_seq_watermarks": {
      "prod:agent-adversarial-reviewer": 3,
      "prod:agent-analytics-engineer": 1735,
      "prod:agent-antigravity": 1,
      "prod:agent-antigravity-argon-architect": 6,
      "prod:agent-antigravity-opus": 8,
      "prod:agent-config-engineer": 460,
      "prod:agent-infra-sre": 1,
      "prod:agent-momo": 97,
      "prod:agent-momo-s190811": 4,
      "prod:agent-momo-s190812": 3,
      "prod:agent-orchestrator": 126,
      "prod:agent-owner": 159,
      "prod:agent-qa-gate": 7,
      "prod:agent-test-agent-1": 1700,
      "prod:agent-test-agent-2": 1700,
      "prod:human-owner": 98,
      "prod:human-u_alice": 4,
      "prod:human-u_funnel_1": 450,
      "prod:human-u_nsm_1": 180,
      "prod:human-u_nsm_2": 90,
      "prod:human-u_nsm_3": 90,
      "prod:system-a2a-router": 2,
      "prod:system-bootstrap": 3,
      "prod:system-coldrestore": 28,
      "prod:system-compact": 284,
      "prod:system-events": 5,
      "prod:system-reaper": 14,
      "prod:system-system": 255,
      "prod:system-watchdog": 20971
    },
    "event_count": 1823,
    "event_hash": "sha256:6536d221c163b0bacb65d15ae7eeb90fe19aa1c3dd0326638501b8d939eb4fd6",
    "until_ts": "2026-11-11T11:58:13.834Z",
    "window": [
      "2026-11-09",
      "2026-11-11"
    ]
  },
  "compacted_from_events": 1823,
  "experiments": {
    "active": 0,
    "killed": 0,
    "shipped": 0,
    "total": 0
  },
  "generated_at": "2026-11-11T11:58:13.835Z",
  "generated_by": "compact.py",
  "growth": {
    "funnel_overall_conversion": 3.0,
    "nsm": 2,
    "paid_users": 3
  },
  "kill_switch": {
    "fail_closed_engaged": false,
    "freshness_s": 113.785707,
    "global": false,
    "read_at": "2026-11-11T11:58:13.755Z",
    "read_from": [
      "K1:state/KILL",
      "K2:env/KILL_SWITCH"
    ],
    "scoped": [],
    "verdict": "running"
  },
  "kpis": {
    "crash_rate": 0.1765,
    "crash_rate_lifetime": 0.1765,
    "crash_rate_sample_sufficient": false,
    "crash_rate_window": 34,
    "receipt_coverage": 1.0,
    "receipts_total": 34
  },
  "open_risks": [],
  "open_tasks": [],
  "phase": "P1-agentic-core",
  "probe_fleet": {
    "asns": [
      "asn:AS1",
      "asn:AS2",
      "asn:AS3"
    ],
    "csr": 1.0,
    "healthy": true
  },
  "schema_version": "2.0.0",
  "sense_level": "Tick-D",
  "workstreams": {
    "agentic-core": {
      "blocked_by": [],
      "health": "unknown",
      "last_receipt": "T-0031",
      "lease": null,
      "open_tasks": [],
      "owner_agent": "antigravity-argon-architect",
      "receipt_chain_head": "sha256:54da13741a2437cf42ea86aaf600d6226bd5106d01924f4e189dad23776745ec",
      "receipt_chain_length": 34
    },
    "main": {
      "blocked_by": [],
      "health": "unknown",
      "last_receipt": null,
      "lease": null,
      "open_tasks": [],
      "owner_agent": "antigravity-opus"
    }
  }
}
```

## Active Handoff (`state/HANDOFF.md`)
# HANDOFF

> وضعیت آخرین نشست کاری به‌صورت خوانا برای انسان. این فایل در پایان هر جلسه کاری بازنویسی می‌شود (Iron Rule 3).
> وضعیت ماشین: `STATE.json` + لاگ رویدادها (`state/events/`) + زنجیره رسیدها (`receipts/`).

> **شروع جلسه جدید؟ ابتدا [`../ONBOARDING.md`](../ONBOARDING.md) را مطالعه کنید.**
> پروتکل کامل Cold-Start، ترتیب مطالعه اسناد، نحوه آغاز جلسه FSP، اعتبارسنجی خط مبنا، نحوه انتخاب تسک بعدی، اقدامات ممنوعه و رویه الزامی پایان جلسه در آن مستند شده است.

- **Updated:** 2026-11-11
- **By:** antigravity-argon-architect (Gemini 3.8 Flash High / Antigravity Harness 2.0, session S-115231, fencing token 39)
- **Slice:** **VS-12 Post-Milestone Autonomous Operational Protocol** (Task **`T-0031`** / **`ADR-034`** Git Sync & Closeout)

---

## Where we are (وضعیت جاری و خلاصه اقدامات انجام‌شده)

معماری کامل **Harness 2.0 & Argon-Grade Deep Reasoning** از سند مرجع `https://share.gemini.google/qAjccclyXYOw` با تطبیق کامل بر SSoT مخزن، استاندارد `ADR-030` (Prefix Caching) و بودجهٔ زمانی هوک‌ها (`CLAUDE.md §6`) پیاده‌سازی، راستی‌آزمایی و با ریموت همگام‌سازی شد (`ADR-034`، رسید `T-0031`):

1. **همگام‌سازی با مخزن ریموت (`origin/main`):** دریافت و rebase تمیز ۱۳ کامیت ورودی ربات گیت‌هاب بدون تعارض و هم‌راستاسازی کامل شاخهٔ محلی با ریموت.
2. **تریاژ و بهداشت مخزن:** پاک‌سازی ۱۹ فایل موقت ساب‌ایجنت‌ها تحت `.agents/teamwork/`، حذف ردیابی ۱۶ فایل لاگ شلوغ از ایندکس گیت (`git rm --cached state/logs/*.log`) با حفظ آن‌ها روی دیسک، حذف کش موقت `state/web_memory/` و به‌روزرسانی اصولی `.gitignore` برای جلوگیری از آلودگی مجدد.
3. **هستهٔ شناختی همیشه فعال (`GEMINI.md`):** ادغام قوانین Boris Cherny، ابزارهای CLI عملیاتی و GRAVITAS با هستهٔ Harness 2.0 (مهار آسیب‌های Flash 3.8، خوانش کل‌نگر، بودجهٔ ۶۰/۲۰/۲۰، و اینواریانت‌های `I1`–`I17`).
4. **پیکربندی MCP و هوک‌های Antigravity (`.agents/mcp_config.json`, `.agents/hooks.json`):** اتصال هرمتیک `marzneshin-agentmemory` روی `./state`؛ اتصال هوک‌های `SessionStart`/`Stop` به `scripts/fsp.py status` و `PostToolUse` به حسگر سریع `scripts/verify.py --lint-imports --lint-clock` (~0.38s به‌جای `health.py --skip-sim` ۱۱۸ ثانیه‌ای).
5. **قوانین و مهارت‌ها (`.agents/rules/`, `.agents/skills/`, `.agents/agents/`):** افزودن `argon-deep-reasoning.md` (`model_decision`)، `marzneshin-code-invariants.md` (`glob`)، چهار مهارت `/fsp-start`، `/sim-tdd`، `/fsp-closeout`، `/scar-learn` و ممیز خواندنی `argon-critic.md` با حفظ کامل زیرماژول `.agents/skills/relevance-ai`.
6. **آشتی کلید توقف اضطراری (Kill Switch Reconcile):** بازگردانی وضعیت تمیز و اجرای `killswitch.py reconcile` برای رفع مقادیر تست و برقراری وضعیت `running (0 active)`، `L2 permitted=True` با شناسایی رسمی عامل `antigravity-argon-architect`.
7. **تست و ممیزی مستقل (`tests/test_argon_harness.py`, `ADR-034`):** ۷ تست جدید واحد، ممیزی `adversarial-reviewer` (PASS)، اسکن AgentShield (0 CRITICAL/HIGH)، گیت‌های `verify.py --all` (6/6) و مجموعهٔ کامل `health.py` (478/478 تست، 6/6 بررسی و 51/51 سناریوی شبیه‌سازی سبز).

---

## Baseline health

- **Unit tests:** 478 / 478 passing (`python3 scripts/health.py`)
- **Verification checks:** 6 / 6 passing (`python3 scripts/verify.py --all`)
- **Simulation scenarios:** 51 / 51 passing (`python3 scripts/sim.py run --all --seeds 11,27,43`)
- **Kill switch:** Running (`global=False`, `L2 permitted=True`, all sources clear)
- **Latest receipt:** `T-0031` (`chain_index: 33`)

---

## Misleading non-regressions observed

- در محیط WSL، اجرای `.venv/bin/python3 scripts/health.py` ۴ خطای import برای ماژول‌های `fastapi` و `langgraph` می‌دهد زیرا این وابستگی‌ها روی `python3` سیستم نصب هستند و نه داخل `.venv`؛ با `python3` سیستم همهٔ ۴۷۸/۴۷۸ تست سبز هستند.
- اجرای تست‌های واحد (به‌ویژه `test_gateway.py`) روی درخت کاری زنده، فایل‌های `state/KILL` و `state/KILL.heartbeat.json` را با هویت‌های تست (`test-operator` و `test-gateway`) تغییر می‌دهد؛ پس از اجرای `health.py`، بازیابی نسخه تمیز و اجرای `killswitch.py reconcile` برای پاکسازی الزامی است. در تسک بعدی (`T-0032`) باید با تعریف متغیر محیطی یا ایزوله‌سازی `MARZNESHIN_OPS_ROOT` در تست‌ها، از نوشتن تست‌ها روی `state/` زنده مخزن جلوگیری شود.
- همچنین Chrome remote debugging (`DevToolsActivePort`) در محیط ویندوز فعال نبود؛ خوانش لینک `share.gemini.google` با رندر ایزولهٔ headless Edge انجام شد.

---

## Open Owner blockers (Oxx)

- **O1:** تایید قیمت‌گذاری نهایی مدل‌ها برای `forecast()` دقیق بودجه (`TRADEOFF-REGISTER.md` T18).
- **O3:** کلید/توکن GitHub Actions برای اجرای زندهٔ برخی مسیرهای ازراه‌دور.
- **O4:** کانال هشدار خارج از باند (OOB) عملیاتی.
- **IDE Remote Debugging / Local Daemons:** در صورت نیاز به ساب‌ایجنت `browser` در چت‌های بعدی، فعال‌سازی `chrome://inspect/#remote-debugging` در Chrome و بررسی لاگ `agentmemory` (`state/logs/agentmemory.log`) و پورت `ccr` (`3456`/`3459`).

---

## Next session — start here

1. شروع تسک **`T-0032`**: ایزوله‌سازی `MARZNESHIN_OPS_ROOT` در تست‌های واحد پایتون تا اجرای `health.py` هیچ‌گاه فایل‌های زنده `state/` را آلوده نکند.
2. اجرای `/fsp-start` (یا `python3 scripts/fsp.py status && python3 scripts/health.py`) با `python3` سیستم.
3. پایش سلامت ۱۲ سرویس محلی با `python3 scripts/dev.py status` و فعال بودن تایمر نگهبان `marzneshin-watchdog.timer`.
