# عرش الرحمان (noorlib-mcp)

[فارسی](#فارسی) | [English](#english) | [العربية](#العربية)

## فارسی

**یک سرور MCP واحد برای هفت پایگاه خانواده نور** — جستجو، فهرست، متن کامل، ترجمه و تفسیر، همه با رمزگشایی و پاکسازی خودکار.

| پایگاه | پوشش | ابزارها |
|---|---|---|
| **noorlib.ir** — کتابخانه دیجیتال نور | ۱۰۹ هزار کتاب، ۱۵۱ هزار جلد | ۶ ابزار `noorlib_*` |
| **hadith.inoor.ir** — جامع‌الاحادیث | ۳۵۵+ منبع حدیثی | ۴ ابزار `hadith_*` |
| **quran.inoor.ir** — پایگاه جامع قرآنی | متن + ۱۵۶ ترجمه + ۴۱۷ تفسیر | ۶ ابزار `quran_*` |
| **wikinoor.ir** — دانشنامه ویکی‌نور | ۳۳ هزار مقاله کتاب‌شناسی/زندگی‌نامه | ۲ ابزار `wikinoor_*` |
| **qamus.inoor.ir** — لغت‌نامه قاموس نور | ۳۶۹ هزار واژه، ۱۶۳ فرهنگ | ۳ ابزار `qamus_*` |
| **noordoc.ir** — پایگاه پایان‌نامه‌ها | ۱۴۹ هزار پایان‌نامه | ۲ ابزار `noordoc_*` |
| **tarikh.inoor.ir** — پایگاه جامع تاریخ | صدها هزار رویداد تاریخی | ۳ ابزار `tarikh_*` |

> ابزار غیررسمی است و از API عمومی وب‌سایت‌های خانواده نور استفاده می‌کند.
>
> **سازگاری:** با هر دو نسل کتابخانه `mcp` کار می‌کند — نسخه 1.x (`FastMCP`) و 2.x (`MCPServer`).

## ۲۶ ابزار

### noorlib.ir — کتابخانه دیجیتال

| ابزار | کار |
|---|---|
| `noorlib_search` | جستجوی کلی در کل کتابخانه (عنوان/مؤلف/اسنیپت) |
| `noorlib_book_info` | متادیتای کتاب (عنوان، پدیدآور، جلد، رایگان؟) |
| `noorlib_book_toc` | فهرست مطالب درختی + `zone` (بازه صفحه هر بخش) |
| `noorlib_book_page` | متن کامل یک صفحه (رمزگشایی + متن ساده + تصویر اسکن) |
| `noorlib_search_in_book` | جستجو داخل یک کتاب → اسنیپت + شماره صفحه/بخش |
| `noorlib_find_pages` | ایندکس سریع: صفحه‌های حاوی کلمات |

### hadith.inoor.ir — جامع‌الاحادیث

| ابزار | کار |
|---|---|
| `hadith_search` | جستجوی متن حدیث (با فیلتر منبع: کافی/بحار/وسائل...) |
| `hadith_by_id` | متن کامل حدیث + سند + مسیر کتاب/باب + همان حدیث در منابع دیگر |
| `hadith_sources` | فهرست ۳۵۵+ منبع حدیثی با sourceId |
| `hadith_toc` | فهرست مطالب یک منبع حدیثی |

### quran.inoor.ir — قرآن

| ابزار | کار |
|---|---|
| `quran_search` | جستجو در متن عربی آیات یا ترجمه‌ها (source=quran/translation) |
| `quran_surahs` | فهرست ۱۱۴ سوره با تعداد آیات |
| `quran_surah_text` | متن کامل یک سوره (۴ خط: عثمان طه/ساده/املایی/مصحف ایران) |
| `quran_ayah_translations` | ترجمه‌های یک آیه از ۱۵۶ ترجمه |
| `quran_ayah_commentary` | تفسیرهای یک آیه (المیزان، نور الثقلین...) — متن کامل |
| `quran_ayah_hadiths` | احادیث مرتبط با آیه (hadithId → hadith_by_id) |

### wikinoor.ir — دانشنامه

| ابزار | کار |
|---|---|
| `wikinoor_search` | جستجوی مقالات (کتاب‌شناسی/زندگی‌نامه) |
| `wikinoor_page` | متن کامل مقاله + جعبه اطلاعات ساختاری (پدیدآور، ناشر، کد noorlib) |

### qamus.inoor.ir — لغت‌نامه

| ابزار | کار |
|---|---|
| `qamus_search` | جستجوی واژه/اصطلاح/نام با معانی |
| `qamus_word` | معانی کامل واژه (ریشه، جمع، مثال) |
| `qamus_dictionaries` | فهرست ۱۶۳ فرهنگ موجود |

### noordoc.ir — پایان‌نامه‌ها

| ابزار | کار |
|---|---|
| `noordoc_search` | جستجوی پایان‌نامه (دانشگاه، مقطع، سال، استاد) |
| `noordoc_thesis` | چکیده + جزئیات کامل پایان‌نامه |

### tarikh.inoor.ir — تاریخ

| ابزار | کار |
|---|---|
| `tarikh_search` | جستجوی رویدادهای تاریخی |
| `tarikh_event` | شرح کامل رویداد + منابع گزارش (با لینک noorlib) |
| `tarikh_today` | رویدادهای امروز (تقویم قمری) |

## نصب

```bash
# در پروژه MCP خودتان (پوشه‌ای مثل MCP-noorlib)
cd ~/MCP-noorlib
python3 -m venv .venv
.venv/bin/pip install noorlib_mcp-3.0.0-py3-none-any.whl
# یا از سورس:
.venv/bin/pip install .
```

## ثبت در Cursor / Claude Desktop

`~/.cursor/mcp.json` (یا `.cursor/mcp.json` پروژه):

```json
{
  "mcpServers": {
    "noor": {
      "command": "/home/ALIZARE84/MCP-noorlib/.venv/bin/noor-mcp"
    }
  }
}
```

> **سه نام، یک برنامه:** هم `noor-mcp`، هم `noorlib-mcp` و هم `arsh-alrahman` (نام پروژه) نصب می‌شوند (هر سه به یک entry point وصل‌اند) — هر کدام را در mcp.json گذاشتید کار می‌کند. اگر قبلاً خطای `namespace "noor" not found` می‌گرفتید، دلیلش همین نام‌گذاری بود؛ الان هر سه نام موجودند.

بعد از تغییر mcp.json، **Cursor را کامل ببندید و دوباره باز کنید** (نه فقط Reload) تا سرور MCP بالا بیاید.

## متغیرهای محیطی

هر پایگاه پیشوند خودش را دارد (`QURAN_MCP_*`, `WIKINOOR_MCP_*`, `QAMUS_MCP_*`, `NOORDOC_MCP_*`, `TARIKH_MCP_*`, `HADITH_MCP_*`, `NOORLIB_MCP_*`) با این کلیدها: `BASE_URL`, `TIMEOUT`, `THROTTLE`, `RETRIES`.

مشترک:

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `NOORLIB_MCP_AUTH` | خالی | توکن لاگین noorlib (`Bearer eyJ...`) برای صفحات شارژی |
| `HADITH_MCP_AUTH` | خالی | توکن لاگین حدیث (معمولاً لازم نیست) |
| `NOORLIB_MCP_USE_PROXY` | `0` | `1` = استفاده از http_proxy/https_proxy سیستم |
| `NOORLIB_MCP_LOG` | `INFO` | `DEBUG` برای لاگ کامل |

> **سیاست پروکسی:** همه کلاینت‌ها پیش‌فرض پروکسی محیطی را نادیده می‌گیرند (`trust_env=False`) تا پروکسی خراب محلی (مثل 127.0.0.1:10808) سرور را زمین نزند؛ با `NOORLIB_MCP_USE_PROXY=1` فعال می‌شود.


## کاتالوگ سریع (bookId noorlib)

تمهید القواعد 1327 · شرح فصوص الحکم 1312 · نصوص الخصوص 11015 · کشف المراد 1236 · توضیح المراد 1198 · شوارق الإلهام 14159 · منشور جاودانه 55202 · نهج‌البلاغه 3542 · بحارالانوار 2564 · تجلیات الهیه 122762 · اسرار عرشیه 122760

### sourceIdهای پرکاربرد hadith.inoor.ir

الکافی (کلینی) — متن کامل ۸ جلد: **1348** · نهج‌البلاغة: 1575 · ترجمه اصول کافی: 2646 · الروضة من الکافی: 2642

## سایت‌های بررسی‌شده و کنارگذاشته

| سایت | علت |
|---|---|
| noormags.ir (مجلات) | به درخواست شما حذف شد |
| hawzah.net (خبری) | جستجو فقط HTML سمت سرور؛ API عمومی جستجو ندارد |
| pajoohyar.ir (پژوهیار) | اپ مدیریت استناددهی؛ نیازمند حساب کاربری |
| andishvaran.ir (اندیشوران) | ASP.NET WebForms با VIEWSTATE؛ جستجو بدون session کار نمی‌کند |
| noorshop / samimnoor / abrenoor / paknevis | فروشگاه/ابزار — بی‌ربط به پژوهش متنی |

## توسعه

```bash
pip install -e ".[dev]"
pytest
```

ساختار:

```
noorlib_mcp/
├── client.py         # httpx async client noorlib + throttle/retry/auth/proxy
├── hadith_client.py  # httpx async client hadith.inoor.ir
├── httpcore.py       # هسته HTTP مشترک (throttle/retry/proxy-safe)
├── quran_client.py   # apiquran.inoor.ir
├── wikinoor_client.py# MediaWiki API
├── qamus_client.py   # qamus-api.inoor.ir
├── noordoc_client.py # noordoc.ir (_search/_content)
├── tarikh_client.py  # tarikh.inoor.ir
├── decoder.py        # رمزگشایی صفحه (base64 → char-swap → shift)
├── server.py         # ۲۶ ابزار MCP (۷ پایگاه)
└── textutil.py       # HTML/wikitext → متن ساده + پاکسازی حدیث
```

## English

**One MCP server for seven Noor-family databases.** Search, browse, and retrieve text, translations, and commentary, with automatic decoding and cleanup.

| Site | Coverage | Tools |
|---|---|---|
| **noorlib.ir** — Noor Digital Library | 109,000 books, 151,000 volumes | 6 `noorlib_*` tools |
| **hadith.inoor.ir** — Comprehensive Hadith | 355+ hadith sources | 4 `hadith_*` tools |
| **quran.inoor.ir** — Quran database | Quran text, 156 translations, 417 commentaries | 6 `quran_*` tools |
| **wikinoor.ir** — Wikinoor encyclopedia | 33,000 bibliographic and biographical articles | 2 `wikinoor_*` tools |
| **qamus.inoor.ir** — Qamus dictionary | 369,000 entries, 163 dictionaries | 3 `qamus_*` tools |
| **noordoc.ir** — Thesis database | 149,000 theses | 2 `noordoc_*` tools |
| **tarikh.inoor.ir** — Historical events | Hundreds of thousands of events | 3 `tarikh_*` tools |

> This unofficial project uses the public APIs of Noor-family websites.
>
> **Compatibility:** Supports both generations of the `mcp` SDK: 1.x (`FastMCP`) and 2.x (`MCPServer`).

### All 26 tools

| Site | Tool | Description |
|---|---|---|
| noorlib.ir | `noorlib_search` | Search books by title, author, or snippet |
| noorlib.ir | `noorlib_book_info` | Book metadata and availability flags |
| noorlib.ir | `noorlib_book_toc` | Hierarchical table of contents and page ranges |
| noorlib.ir | `noorlib_book_page` | Read and decode a book page; return scan images when present |
| noorlib.ir | `noorlib_search_in_book` | Search within a book and return snippets and page locations |
| noorlib.ir | `noorlib_find_pages` | Find pages containing query terms |
| hadith.inoor.ir | `hadith_search` | Search hadith text and optionally filter by source |
| hadith.inoor.ir | `hadith_by_id` | Full hadith, chain, book path, and related-source records |
| hadith.inoor.ir | `hadith_sources` | List hadith sources and their IDs |
| hadith.inoor.ir | `hadith_toc` | Browse a source's table of contents |
| quran.inoor.ir | `quran_search` | Search Quran text or translations |
| quran.inoor.ir | `quran_surahs` | List the 114 surahs and verse counts |
| quran.inoor.ir | `quran_surah_text` | Retrieve a surah in a selected orthography |
| quran.inoor.ir | `quran_ayah_translations` | Retrieve translations of a verse |
| quran.inoor.ir | `quran_ayah_commentary` | Retrieve verse commentaries, including Al-Mizan |
| quran.inoor.ir | `quran_ayah_hadiths` | Find hadith groups related to a verse |
| wikinoor.ir | `wikinoor_search` | Search bibliographic and biographical articles |
| wikinoor.ir | `wikinoor_page` | Retrieve article text and structured infobox fields |
| qamus.inoor.ir | `qamus_search` | Search words, terms, or names and their meanings |
| qamus.inoor.ir | `qamus_word` | Retrieve full word details and meanings |
| qamus.inoor.ir | `qamus_dictionaries` | List available dictionaries |
| noordoc.ir | `noordoc_search` | Search theses by title and metadata |
| noordoc.ir | `noordoc_thesis` | Retrieve a thesis abstract and metadata |
| tarikh.inoor.ir | `tarikh_search` | Search historical events |
| tarikh.inoor.ir | `tarikh_event` | Retrieve an event description and cited sources |
| tarikh.inoor.ir | `tarikh_today` | List events for the current Hijri date |

### Installation

```bash
cd ~/MCP-noorlib
python3 -m venv .venv
.venv/bin/pip install noorlib_mcp-3.0.0-py3-none-any.whl
# Or install from source:
.venv/bin/pip install .
```

### Configure Cursor or Claude Desktop

Add the server to `~/.cursor/mcp.json` or the project's `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "noor": {
      "command": "/home/USERNAME/MCP-noorlib/.venv/bin/noor-mcp"
    }
  }
}
```

The `noor-mcp`, `noorlib-mcp`, and `arsh-alrahman` commands all launch the same server. Use the full path to the command. After changing the MCP configuration, fully restart Cursor or Claude Desktop.

### Environment variables

Each site accepts its own `BASE_URL`, `TIMEOUT`, `THROTTLE`, and `RETRIES` variables, prefixed with `QURAN_MCP_`, `WIKINOOR_MCP_`, `QAMUS_MCP_`, `NOORDOC_MCP_`, `TARIKH_MCP_`, `HADITH_MCP_`, or `NOORLIB_MCP_`.

| Variable | Default | Description |
|---|---|---|
| `NOORLIB_MCP_AUTH` | empty | Noorlib bearer token for pages that require study credit |
| `HADITH_MCP_AUTH` | empty | Hadith-site bearer token; usually not needed |
| `NOORLIB_MCP_USE_PROXY` | `0` | Set to `1` to honor system `http_proxy`/`https_proxy` settings |
| `NOORLIB_MCP_LOG` | `INFO` | Set to `DEBUG` for detailed logs |

All clients ignore proxy environment variables by default (`trust_env=False`). Set `NOORLIB_MCP_USE_PROXY=1` to opt in.

### Access and payment

- **Noorlib:** Search snippets are free. Reading some full book pages may consume study credit; set `NOORLIB_MCP_AUTH` to a logged-in bearer token for eligible pages. The server returns the site's validation message when credit is required.
- **Noordoc:** Search results, thesis metadata, abstracts, and page inventory are exposed. The thesis page content (PDF/images) requires a paid account and is intentionally not exposed.
- The other integrations do not require payment or authentication in this project's documented API flows. The websites' own terms and access policies still apply.

For Noorlib, `page_number` is counted within a section, not across the whole book. Get `sectionNumber` from the `zone` field returned by `noorlib_book_toc`.

### Technical notes

- Noorlib page decoding: URL-safe Base64 → UTF-8 → swap adjacent characters → subtract the page number from each character code. Swapping Unicode characters (not bytes) preserves Persian and Arabic text.
- Quran search responses are double-encoded JSON. Commentary and related-hadith endpoints require the full parameter set.
- Wikinoor uses the standard MediaWiki API; article text is converted from wikitext and infobox fields are extracted.
- Qamus word details require the `X-Api-Version: 2` header.
- Noordoc thesis file contents are behind a paid aggregator endpoint and are not exposed by this server.
- Tarikh event dates use a variable-length Hijri year followed by month and day.

### Development

```bash
pip install -e ".[dev]"
pytest
```

The package is organized around one client per site, a shared HTTP core for the lighter APIs, `server.py` for MCP tools, and `textutil.py`/`decoder.py` for content cleanup and Noorlib page decoding.

## العربية

**خادم MCP واحد لقواعد بيانات عائلة نور السبع.** يوفّر البحث والتصفّح واسترجاع النصوص والترجمات والتفاسير، مع فك الترميز والتنظيف تلقائياً.

| الموقع | المحتوى | الأدوات |
|---|---|---|
| **noorlib.ir** — مكتبة نور الرقمية | 109 آلاف كتاب و151 ألف مجلد | 6 أدوات `noorlib_*` |
| **hadith.inoor.ir** — جامع الأحاديث | أكثر من 355 مصدراً حديثياً | 4 أدوات `hadith_*` |
| **quran.inoor.ir** — قاعدة القرآن | نص القرآن و156 ترجمة و417 تفسيراً | 6 أدوات `quran_*` |
| **wikinoor.ir** — موسوعة ويكي نور | 33 ألف مقالة ببليوغرافية وسِيَرية | أداتان `wikinoor_*` |
| **qamus.inoor.ir** — قاموس نور | 369 ألف مدخل و163 معجماً | 3 أدوات `qamus_*` |
| **noordoc.ir** — قاعدة الرسائل الجامعية | 149 ألف رسالة | أداتان `noordoc_*` |
| **tarikh.inoor.ir** — قاعدة التاريخ | مئات آلاف الأحداث التاريخية | 3 أدوات `tarikh_*` |

> هذا مشروع غير رسمي يستخدم واجهات API العامة لمواقع عائلة نور.
>
> **التوافق:** يدعم الإصدارين الرئيسيين من مكتبة `mcp`: الإصدار 1.x (`FastMCP`) والإصدار 2.x (`MCPServer`).

### الأدوات الـ 26

| الموقع | الأداة | الوصف |
|---|---|---|
| noorlib.ir | `noorlib_search` | البحث عن الكتب بالعنوان أو المؤلف أو المقتطف |
| noorlib.ir | `noorlib_book_info` | بيانات الكتاب ومؤشرات توفره |
| noorlib.ir | `noorlib_book_toc` | فهرس هرمي ونطاقات الصفحات |
| noorlib.ir | `noorlib_book_page` | قراءة صفحة وفك ترميزها، وإرجاع صور المسح عند وجودها |
| noorlib.ir | `noorlib_search_in_book` | البحث داخل كتاب وإرجاع المقتطفات ومواضع الصفحات |
| noorlib.ir | `noorlib_find_pages` | العثور على الصفحات التي تحتوي كلمات البحث |
| hadith.inoor.ir | `hadith_search` | البحث في نص الحديث مع إمكانية التصفية حسب المصدر |
| hadith.inoor.ir | `hadith_by_id` | نص الحديث وسنده ومساره في الكتاب ومواضعه في مصادر أخرى |
| hadith.inoor.ir | `hadith_sources` | عرض مصادر الحديث ومعرّفاتها |
| hadith.inoor.ir | `hadith_toc` | تصفح فهرس مصدر حديثي |
| quran.inoor.ir | `quran_search` | البحث في نص القرآن أو الترجمات |
| quran.inoor.ir | `quran_surahs` | عرض السور الـ 114 وعدد آياتها |
| quran.inoor.ir | `quran_surah_text` | استرجاع نص سورة برسم مختار |
| quran.inoor.ir | `quran_ayah_translations` | استرجاع ترجمات آية |
| quran.inoor.ir | `quran_ayah_commentary` | استرجاع تفاسير الآية، ومنها تفسير الميزان |
| quran.inoor.ir | `quran_ayah_hadiths` | العثور على مجموعات الأحاديث المرتبطة بآية |
| wikinoor.ir | `wikinoor_search` | البحث في المقالات الببليوغرافية والسِيَرية |
| wikinoor.ir | `wikinoor_page` | استرجاع نص المقال وحقول صندوق المعلومات المنظّمة |
| qamus.inoor.ir | `qamus_search` | البحث عن الكلمات أو المصطلحات أو الأسماء ومعانيها |
| qamus.inoor.ir | `qamus_word` | استرجاع تفاصيل الكلمة ومعانيها كاملة |
| qamus.inoor.ir | `qamus_dictionaries` | عرض المعاجم المتاحة |
| noordoc.ir | `noordoc_search` | البحث عن الرسائل الجامعية وبياناتها |
| noordoc.ir | `noordoc_thesis` | استرجاع ملخص الرسالة وبياناتها |
| tarikh.inoor.ir | `tarikh_search` | البحث عن الأحداث التاريخية |
| tarikh.inoor.ir | `tarikh_event` | استرجاع شرح الحدث ومصادره |
| tarikh.inoor.ir | `tarikh_today` | عرض أحداث اليوم حسب التقويم الهجري |

### التثبيت

```bash
cd ~/MCP-noorlib
python3 -m venv .venv
.venv/bin/pip install noorlib_mcp-3.0.0-py3-none-any.whl
# أو التثبيت من المصدر:
.venv/bin/pip install .
```

### إعداد Cursor أو Claude Desktop

أضف الخادم إلى `~/.cursor/mcp.json` أو إلى `.cursor/mcp.json` داخل المشروع:

```json
{
  "mcpServers": {
    "noor": {
      "command": "/home/USERNAME/MCP-noorlib/.venv/bin/noor-mcp"
    }
  }
}
```

الأوامر `noor-mcp` و`noorlib-mcp` و`arsh-alrahman` تشغّل الخادم نفسه. استخدم المسار الكامل للأمر، ثم أعد تشغيل Cursor أو Claude Desktop بالكامل بعد تعديل الإعدادات.

### متغيرات البيئة

لكل موقع المتغيرات `BASE_URL` و`TIMEOUT` و`THROTTLE` و`RETRIES` مع بادئة خاصة به: `QURAN_MCP_` أو `WIKINOOR_MCP_` أو `QAMUS_MCP_` أو `NOORDOC_MCP_` أو `TARIKH_MCP_` أو `HADITH_MCP_` أو `NOORLIB_MCP_`.

| المتغير | القيمة الافتراضية | الوصف |
|---|---|---|
| `NOORLIB_MCP_AUTH` | فارغ | رمز Bearer لحساب نورلایب لقراءة الصفحات التي تتطلب رصيد دراسة |
| `HADITH_MCP_AUTH` | فارغ | رمز Bearer لموقع الحديث؛ غالباً لا يلزم |
| `NOORLIB_MCP_USE_PROXY` | `0` | اضبطه على `1` لاستخدام إعدادات `http_proxy` و`https_proxy` للنظام |
| `NOORLIB_MCP_LOG` | `INFO` | اضبطه على `DEBUG` للحصول على سجلات مفصلة |

تتجاهل جميع العملاء متغيرات البروكسي افتراضياً (`trust_env=False`). اضبط `NOORLIB_MCP_USE_PROXY=1` لتفعيلها.

### الوصول والدفع

- **نورلایب:** مقتطفات نتائج البحث مجانية. قد تتطلب قراءة بعض صفحات الكتب رصيد دراسة؛ ضع رمز Bearer لحساب مسجّل في `NOORLIB_MCP_AUTH` للصفحات المؤهلة. يعيد الخادم رسالة التحقق الصادرة عن الموقع عند الحاجة إلى رصيد.
- **نورداك:** البحث وبيانات الرسائل والملخصات وفهرس الصفحات متاحة. أما محتوى صفحات الرسالة (ملفات PDF والصور) فيتطلب حساباً مدفوعاً، ولذلك لا يقدمه هذا الخادم.
- لا يتطلب استخدام واجهات المواقع الأخرى في تدفقات هذا المشروع دفعاً أو مصادقة. تظل شروط الوصول وسياسات المواقع نفسها سارية.

في نورلایب، يُحسب `page_number` داخل القسم لا على مستوى الكتاب كله. خذ `sectionNumber` من الحقل `zone` الذي تعيده الأداة `noorlib_book_toc`.

### ملاحظات تقنية

- فك صفحات نورلایب: Base64 آمن لعناوين URL ← UTF-8 ← تبديل الأحرف المتجاورة ← طرح رقم الصفحة من رمز كل حرف. يجري التبديل على محارف Unicode لا على البايتات للحفاظ على النص العربي والفارسي.
- استجابات البحث في القرآن مشفّرة بصيغة JSON مرتين. وتتطلب واجهات التفسير والأحاديث المرتبطة جميع المعاملات.
- يستخدم ويكي نور واجهة MediaWiki القياسية؛ ويُنظّف نص المقال المستخرج من wikitext وتُستخرج حقول صندوق المعلومات.
- تتطلب تفاصيل الكلمات في قاموس نور الترويسة `X-Api-Version: 2`.
- محتوى ملفات الرسائل في نورداك خلف واجهة وسيطة مدفوعة ولا يتيحه هذا الخادم.
- تواريخ أحداث موقع التاريخ تتكون من سنة هجرية متغيرة الطول يتبعها الشهر واليوم.

### التطوير

```bash
pip install -e ".[dev]"
pytest
```

تتضمن الحزمة عميلاً لكل موقع، ونواة HTTP مشتركة للواجهات الأخف، وملف `server.py` لأدوات MCP، وملفي `textutil.py` و`decoder.py` لتنظيف المحتوى وفك صفحات نورلایب.
