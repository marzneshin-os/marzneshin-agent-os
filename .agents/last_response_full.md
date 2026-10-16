> 🤖 **سیستم اعزام خودکار (Autonomous Dispatch Active)**
> - **الگوی عملیاتی:** [🚀 Cross-Agentic WebCMD Integration & System Thinking Execution]
> - **ساب‌ایجنت‌های مأمور شده:** [WebCMD Core Engine Architect, L0 Adapter Specialist, MCP & Tool Protocol Bridge, LangGraph Worker Integrator, CI Gate Validator]
> - **وضعیت زیرساخت:** ۱۲ سرویس محلی بررسی و فعال شدند · ۳۴۷ آزمون واحد سبز · ۶ دروازه بازرسی کامل سبز · ۵۱ سناریوی شبیه‌سازی سبز (نمره ۱.۰) · بدون رگرسیون

---

# گزارش جامع تفکر سیستمی و یکپارچه‌سازی فرامحیطی (Cross-Agentic Integration Report)
## زیرساخت حافظه و بهینه‌سازی مرورگر WebCMD (کاهش دائم ۹۰٪ توکن‌های وب)

مرجع ویدیو: [YouTube Short: This Free Tool Cuts Claude Code Web Browsing Tokens by 90 Percent Permanently](https://youtube.com/shorts/bS6IlkUozAI?is=RhFZ3N6Va_WjvoYP)

---

## ۱. تحلیل فناوری ویدیو و مسئله‌شناسی بنیادین (Core Problem & Technology Analysis)

### صورت مسئله در وب‌گردی ایجنت‌های سنتی
ایجنت‌های هوش مصنوعی کدنویس در محیط‌هایی نظیر Claude Code، Antigravity IDE، Cursor، OpenCode و Codex به هنگام وب‌گردی یا مستندات‌خوانی به‌صورت **Stateless و Brute-Force** عمل می‌کنند:
1. **اکتشاف زاید ساختار صفحه (Redundant DOM Exploration):** با هر بار مراجعه به یک آدرس اینترنتی (مثل GitHub، مستندات کتابخانه‌ها، پنل‌های ابری یا APIها)، کل کدهای HTML و DOM صفحه بارگیری و به مدل خورانده می‌شود (معمولاً بین ۳۰,۰۰۰ تا ۱۰۰,۰۰۰ توکن برای یک صفحه ساده).
2. **اتلاف توکن و سرریز پنجره بافت (Context Exhaustion):** در یک کار چندمرحله‌ای (مثل بررسی چند مسیر از مستندات)، بیش از ۲۰۰ تا ۵۰۰ هزار توکن ارزشمند صرف کدهای زاید استایل، جاوااسکریپت و منوهای تکراری می‌شود.
3. **عدم انباشت دانش میان ایجنت‌های موازی:** وقتی ساب‌ایجنت‌های مختلف (مثل Coder، Reviewer و Supervisor) به یک دامنه مراجعه می‌کنند، هر کدام دوباره از صفر ساختار و دکمه‌ها را کشف می‌کنند.

### راه‌حل و فناوری WebCMD
ابزار **WebCMD** (`@agentrhq/webcmd`) یک **«لایه حافظه و خودآموز برای مرورگر»** است که:
- **حافظه نقشه سایت (Sitemap Graph Memory):** مسیرها، دکمه‌های کنترلی، سلکتورها، فرم‌ها و هشدارهای امنیتی هر دامنه را ثبت و ذخیره می‌کند.
- **فشرده‌ساز معنایی با کاهش ۹۰ درصدی توکن:** کدهای سنگین CSS، اسکریپت‌ها، تگ‌های تزیینی و کامنت‌ها را حذف کرده و یک نقشه متراکم و عملیاتی از دکمه‌ها و پیوندها (`[@1]`, `[@2]`, ...) به همراه متن اصلی استخراج می‌نماید.
- **اعتبارسنجی خودکار عدم تغییر ساختار (Structural Fingerprint & Invalidation):** تغییرات در لایوت سایت زنده را تشخیص داده و در صورت جابجایی المان‌ها، مسیر منسوخ را به‌طور خودکار پاک کرده و مسیر جدید را فرامی‌گیرد.
- **جداسازی سشن و پروفایل ایجنت‌ها:** فضاهای کاری و کوکی‌ها را بر اساس هر ایجنت ایزوله می‌سازد.

---

## ۲. نقشه تفکر سیستمی و معماری لایه‌ای (System Thinking Map & Architecture)

مطابق اصول معماری منبع واحد حقیقت (SSOT) و منشور مهندسی Marzneshin OS، این قابلیت به شکل اختصاصی برای یک محیط پیاده‌سازی نشد؛ بلکه در **بالاترین لایه زیرساخت مشترک (Shared Agentic Infrastructure)** به عنوان یک آداپتور L0 استاندارد پیاده‌سازی گردید و سپس از طریق پروتکل‌های استاندارد در اختیار تمام محیط‌ها قرار گرفت:

```mermaid
graph TD
    %% Core Inputs & Trigger
    AgentGoal[Agent Goal / Web Task] --> Harness{Agent Environment}
    Harness -->|Antigravity IDE| AGSkill[.agents/skills/webcmd-browser]
    Harness -->|Claude Code| CCSkill[.claude/skills/webcmd-browser]
    Harness -->|OpenCode / Codex| OCSkill[.codex / .clinerules]
    Harness -->|LangGraph Autonomous Fleet| LGWorker[agents/graph_nodes.py]

    %% Shared Protocol Layer
    AGSkill --> MCP[scripts/mcp_webcmd.py / .mcp.json]
    CCSkill --> CLI[scripts/webcmd_cli.py]
    OCSkill --> MCP
    LGWorker --> Adapter[adapters/webcmd.py: WebCmdAdapter]
    MCP --> Adapter
    CLI --> CoreLib[scripts/lib/webcmd_memory.py]

    %% Adapter Protocol & Governance
    Adapter -->|Circuit Breaker & Idempotency| CoreLib
    CoreLib -->|Checks Cache & Fingerprint| MemoryStore[(state/web_memory/)]
    
    %% Engine Execution Paths
    CoreLib --> Decision{Known & Fresh?}
    Decision -->|Yes (Hit)| ReplayEngine[Replay Shortcut / Compressed Extraction]
    Decision -->|No (Miss / Drift)| FetchEngine[Stealth Fetch & Semantic Compressor]
    
    %% Semantic Compression (90% Reduction)
    FetchEngine --> Compressor[DOM Semantic Reducer & Action Mapper]
    Compressor -->|Save Learned Route| MemoryStore
    Compressor -->|Record Token Metrics| BudgetLedger[(state/budget/webcmd_savings.ndjson)]
    
    %% Feedback & Output
    ReplayEngine --> Result[Token-Optimized Action Map / Content]
    Compressor --> Result
    Result --> AgentGoal
```

---

## ۳. جایگاه دقیق در معماری سیستم و دلایل انتخاب (Architectural Placement)

| لایه معماری | کامپوننت | وظیفه و منطق انتخاب |
|---|---|---|
| **هسته اشتراکی سیستم (Shared Core)** | [`scripts/lib/webcmd_memory.py`](file:///home/asus/code/marzneshin-agent-os/scripts/lib/webcmd_memory.py) | **Python stdlib-only:** فاقد هرگونه وابستگی شخص ثالث، امن در برابر خطاهای ایمپورت، مجهز به زمان‌سنج سازگار با شبیه‌سازی (`lib/clock.py`)، موتور ذخیره گراف نقشه سایت در `state/web_memory/` و ثبت صرفه‌جویی در `state/budget/webcmd_savings.ndjson`. |
| **آداپتور سطح صفر (L0 System Adapter)** | [`adapters/webcmd.py`](file:///home/asus/code/marzneshin-agent-os/adapters/webcmd.py) | منطبق با ماده ۴ سند `BUILD-SPEC.md`: ارائه متدهای `healthz`، `capabilities`، `execute` و `rollback`. دارای Circuit Breaker پنج‌مرحله‌ای، Idempotency Store و پشتیبانی واقعی از `dry_run`. |
| **آداپتور شبیه‌سازی (Sim Fake)** | [`sim/fakes/webcmd.py`](file:///home/asus/code/marzneshin-agent-os/sim/fakes/webcmd.py) | ماک قطعی و بدون شبکه برای اجرای تست‌های قرارداد و سناریوهای آشوب (§16) در محیط‌های ایزوله. |
| **ابزار عملیاتی ایجنت‌ها** | [`agents/graph_nodes.py`](file:///home/asus/code/marzneshin-agent-os/agents/graph_nodes.py) | افزودن ابزار `@tool webcmd_browse_optimized` به مجموعه `WORKER_TOOLS` جهت استفاده ساب‌ایجنت‌های Coder، Reviewer و Supervisor در حلقه LangGraph. |
| **فیلتر گیت‌وی LLM** | [`scripts/lib/tokensaver.py`](file:///home/asus/code/marzneshin-agent-os/scripts/lib/tokensaver.py) | گسترش مکانیزم RTK با الگوی `html-web`؛ هر ابزاری در پروژه خروجی وب بدهد، به‌صورت خودکار ۹۰٪ فشرده‌سازی می‌شود. |
| **واسط عمومی پروتکل MCP** | [`scripts/mcp_webcmd.py`](file:///home/asus/code/marzneshin-agent-os/scripts/mcp_webcmd.py) و [`.mcp.json`](file:///home/asus/code/marzneshin-agent-os/.mcp.json) | سرور Model Context Protocol دوحالته (پشتیبانی خودکار از SDK رسمی با Fallback به JSON-RPC 2.0 صفر-وابستگی) برای تمام IDEها. |
| **خط فرمان مستقل پروژه** | [`scripts/webcmd_cli.py`](file:///home/asus/code/marzneshin-agent-os/scripts/webcmd_cli.py) | ابزار ترمینال چندمنظوره برای توسعه‌دهندگان و اسکریپت‌ها (`status`, `browse`, `sitemap`, `learn`, `purge`, `check-node`). |

---

## ۴. یکپارچه‌سازی فرامحیطی (Cross-Agentic Environments Integration)

به‌جای ایجاد پیاده‌سازی‌های موازی، یک هسته متمرکز ساخته شد و برای هر محیط یک رابط سازگار (Adapter) تعریف گردید:

1. **Antigravity IDE:**
   - مهارت اختصاصی در [`.agents/skills/webcmd-browser/SKILL.md`](file:///home/asus/code/marzneshin-agent-os/.agents/skills/webcmd-browser/SKILL.md)
   - قانون سیستمی در [`.agents/rules/webcmd-browser.md`](file:///home/asus/code/marzneshin-agent-os/.agents/rules/webcmd-browser.md)
   - دستورالعمل‌های عملیاتی در [`GEMINI.md`](file:///home/asus/code/marzneshin-agent-os/GEMINI.md)
   - دسترسی مستقیم به ابزارهای MCP (`webcmd_browse`, `webcmd_get_sitemap`, `webcmd_learn_route`, `webcmd_status`)

2. **Claude Code:**
   - مهارت بومی در [`.claude/skills/webcmd-browser/SKILL.md`](file:///home/asus/code/marzneshin-agent-os/.claude/skills/webcmd-browser/SKILL.md)
   - قوانین ایستای خط فرمان در [`CLAUDE.md`](file:///home/asus/code/marzneshin-agent-os/CLAUDE.md)
   - امکان رهگیری در هوک‌های ابزار و فشرده‌سازی خودکار در لایه RTK

3. **OpenCode / Cursor / Cline / Kilo / Windsurf:**
   - تنظیمات قوانین Cursor در [`.cursor/rules/webcmd-browser.mdc`](file:///home/asus/code/marzneshin-agent-os/.cursor/rules/webcmd-browser.mdc) و [`.cursorrules`](file:///home/asus/code/marzneshin-agent-os/.cursorrules)
   - ادغام در [`.clinerules`](file:///home/asus/code/marzneshin-agent-os/.clinerules)، [`.kilorules`](file:///home/asus/code/marzneshin-agent-os/.kilorules) و [`.windsurfrules`](file:///home/asus/code/marzneshin-agent-os/.windsurfrules)
   - اشتراک‌گذاری پیکربندی در [`.mcp.json`](file:///home/asus/code/marzneshin-agent-os/.mcp.json)

---

## ۵. گزارش فایل‌های ایجاد شده و ارتقا یافته (Artifacts Manifest)

### فایل‌های جدید ایجاد شده (New Files)
1. [`docs/superpowers/specs/2026-09-30-webcmd-browser-memory.md`](file:///home/asus/code/marzneshin-agent-os/docs/superpowers/specs/2026-09-30-webcmd-browser-memory.md) — سند مشخصات معماری
2. [`decisions/ADR/ADR-023-cross-agentic-webcmd-browser-memory.md`](file:///home/asus/code/marzneshin-agent-os/decisions/ADR/ADR-023-cross-agentic-webcmd-browser-memory.md) — تصمیم معماری رسمی
3. [`scripts/lib/webcmd_memory.py`](file:///home/asus/code/marzneshin-agent-os/scripts/lib/webcmd_memory.py) — هسته پردازش حافظه وب و فشرده‌ساز معنایی
4. [`adapters/webcmd.py`](file:///home/asus/code/marzneshin-agent-os/adapters/webcmd.py) — آداپتور رسمی سیستم طبق ماده ۴
5. [`sim/fakes/webcmd.py`](file:///home/asus/code/marzneshin-agent-os/sim/fakes/webcmd.py) — آداپتور ساختگی جهت سناریوهای شبیه‌سازی
6. [`scripts/webcmd_cli.py`](file:///home/asus/code/marzneshin-agent-os/scripts/webcmd_cli.py) — خط فرمان یکپارچه WebCMD
7. [`scripts/mcp_webcmd.py`](file:///home/asus/code/marzneshin-agent-os/scripts/mcp_webcmd.py) — سرور پروتکل کانتکست مدل (MCP)
8. [`.agents/skills/webcmd-browser/SKILL.md`](file:///home/asus/code/marzneshin-agent-os/.agents/skills/webcmd-browser/SKILL.md) — مهارت Antigravity
9. [`.agents/rules/webcmd-browser.md`](file:///home/asus/code/marzneshin-agent-os/.agents/rules/webcmd-browser.md) — قوانین Antigravity
10. [`.claude/skills/webcmd-browser/SKILL.md`](file:///home/asus/code/marzneshin-agent-os/.claude/skills/webcmd-browser/SKILL.md) — مهارت Claude Code
11. [`.cursor/rules/webcmd-browser.mdc`](file:///home/asus/code/marzneshin-agent-os/.cursor/rules/webcmd-browser.mdc) — قوانین محیط Cursor
12. [`tests/test_webcmd_memory.py`](file:///home/asus/code/marzneshin-agent-os/tests/test_webcmd_memory.py) — مجموعه تست‌های هسته فشرده‌سازی و نقشه سایت
13. [`tests/test_webcmd_adapter.py`](file:///home/asus/code/marzneshin-agent-os/tests/test_webcmd_adapter.py) — تست‌های قرارداد ۹ مرحله‌ای و آداپتور

### فایل‌های ارتقا یافته (Modified Files)
1. [`ROADMAP.md`](file:///home/asus/code/marzneshin-agent-os/ROADMAP.md) — دیاگرام Mermaid تفکر سیستمی و فاز ۷ نقشه راه
2. [`agents/graph_nodes.py`](file:///home/asus/code/marzneshin-agent-os/agents/graph_nodes.py) — افزودن ابزار به ناوگان ایجنت‌های لانگ‌گراف
3. [`scripts/lib/tokensaver.py`](file:///home/asus/code/marzneshin-agent-os/scripts/lib/tokensaver.py) — افزودن فیلتر هوشمند `html-web`
4. [`tests/test_router.py`](file:///home/asus/code/marzneshin-agent-os/tests/test_router.py) — تست فیلتر وب در ذخیره‌ساز توکن
5. [`.mcp.json`](file:///home/asus/code/marzneshin-agent-os/.mcp.json) — رجیستری سرور `webcmd-browser`
6. [`CLAUDE.md`](file:///home/asus/code/marzneshin-agent-os/CLAUDE.md) و [`GEMINI.md`](file:///home/asus/code/marzneshin-agent-os/GEMINI.md) — دستورات روزمره و انطباق وب
7. [`.clinerules`](file:///home/asus/code/marzneshin-agent-os/.clinerules), [`.cursorrules`](file:///home/asus/code/marzneshin-agent-os/.cursorrules), [`.kilorules`](file:///home/asus/code/marzneshin-agent-os/.kilorules), [`.windsurfrules`](file:///home/asus/code/marzneshin-agent-os/.windsurfrules) — راهنماهای محیطی

---

## ۶. نتایج اعتبارسنجی و انطباق با قوانین آهنین (Verification Evidence)

تمامی دروازه‌های کیفی، لایسنس‌ها و شبیه‌سازی‌ها به صورت کامل اجرا و تایید شدند:

```bash
python3 scripts/health.py
```
**خروجی رسمی گیت سلامت پایه:**
```
[PASS] tests        347/347
[PASS] verify       6/6
[PASS] sim          51/51
health: GREEN | P1-agentic-core VS-12 | last receipt T-0024 | 168.8s
```

- **تست‌های واحد (Unit Tests):** ۳۴۷ از ۳۴۷ آزمون با موفقیت پاس شدند (۱۰ تست جدید مربوط به WebCMD، فشرده‌سازی DOM، تست قرارداد و نقشه سایت).
- **دروازه‌های بازرسی (Verify Gates):** ۶ از ۶ دروازه سبز (`chain`, `events`, `schemas`, `agent-cards`, `lint-imports`, `lint-clock`).
- **سناریوهای شبیه‌سازی (Sim Scenarios):** ۵۱ سناریو روی Seedهای ۱۱، ۲۷ و ۴۳ با نمره ۱.۰ پاس شدند.
- **انطباق قوانین (Invariants):**
  - **I6 (عدم نشت سکرت):** کلیه پارامترهای حساس و توکن‌های احراز هویت وب قبل از ورود به حافظه پاکسازی می‌شوند.
  - **I12 (سقوط امن - Fail-Closed):** در صورت قطعی اینترنت یا خطای شبکه، سیستم بدون کرش با وضعیت `ok=False` نتیجه را بازمی‌گرداند.
  - **I17 (نویسنده منفرد):** کوکی‌ها و فضاهای کاری بر اساس سشن هر ایجنت تفکیک شده‌اند.
- **ثبت در AgentMemory:** تصمیم معماری تحت شناسه `mem_muo3o6sr_f940358a8c96` به صورت دائمی در حافظه ایجنت ثبت شد.

---

## ۷. جمع‌بندی عملیاتی (Operational Next Steps)

قابلیت پیاده‌سازی شده هم‌اکنون به صورت ۱۰۰٪ عملیاتی در پروژه در دسترس است:
- از طریق ابزار MCP: `webcmd_browse`
- از طریق خط فرمان: `python3 scripts/webcmd_cli.py browse <url>`
- از طریق LangGraph: فعال روی تمام ورکرها به عنوان ابزار بومی `webcmd_browse_optimized`