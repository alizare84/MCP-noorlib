# عرش الرحمان (noorlib-mcp)

[فارسی](#فارسی) | [English](#english) | [العربية](#العربية)

سرور MCP برای هفت پایگاه خانوادهٔ نور. جستجو، فهرست، متن، ترجمه و تفسیر از یک ورودی در اختیار عامل زبانی قرار می‌گیرد.

این پروژه مستقل است و از رابط عمومی همان وب‌سایت‌ها استفاده می‌کند. با کتابخانهٔ `mcp` نسخهٔ ۱ و ۲ سازگار است.

## فارسی

| پایگاه | پوشش | ابزارها |
|---|---|---|
| **noorlib.ir** — کتابخانهٔ دیجیتال نور | ۱۰۹ هزار کتاب، ۱۵۱ هزار جلد | ۶ ابزار `noorlib_*` |
| **hadith.inoor.ir** — جامع‌الاحادیث | ۳۵۵+ منبع حدیثی | ۵ ابزار `hadith_*` |
| **quran.inoor.ir** — پایگاه جامع قرآنی | متن + ۱۵۶ ترجمه + ۴۱۷ تفسیر | ۶ ابزار `quran_*` |
| **wikinoor.ir** — دانشنامهٔ ویکی‌نور | ۳۳ هزار مقالهٔ کتاب‌شناسی و زندگی‌نامه | ۲ ابزار `wikinoor_*` |
| **qamus.inoor.ir** — لغت‌نامهٔ قاموس نور | ۳۶۹ هزار واژه، ۱۶۳ فرهنگ | ۴ ابزار `qamus_*` |
| **noordoc.ir** — پایگاه پایان‌نامه‌ها | ۱۴۹ هزار پایان‌نامه | ۳ ابزار `noordoc_*` |
| **tarikh.inoor.ir** — پایگاه جامع تاریخ | صدها هزار رویداد | ۳ ابزار `tarikh_*` |

### ابزارها

| ابزار | کار |
|---|---|
| `noorlib_search` | جستجو در عنوان، پدیدآور و اسنیپت |
| `noorlib_book_info` | شناسنامهٔ کتاب، جلدها و وضعیت دسترسی |
| `noorlib_book_toc` | فهرست درختی و بازهٔ صفحهٔ هر بخش (`zone`) |
| `noorlib_book_page` | متن خوانای یک صفحه، و تصویر اسکن در صورت وجود |
| `noorlib_search_in_book` | جستجو داخل یک کتاب، با شمارهٔ صفحه و بخش |
| `noorlib_find_pages` | صفحه‌های حاوی عبارت، با صفحه‌بندی |
| `hadith_search` | جستجوی حدیث، با فیلتر منبع و ترجمه و شرح |
| `hadith_by_id` | متن، سند، مسیر کتاب و باب، و نقل در منابع دیگر |
| `hadith_sources` | فهرست منابع و `sourceId` |
| `hadith_toc` | فهرست یک منبع حدیثی |
| `hadith_related` | حدیث‌های مشابه |
| `quran_search` | جستجو در متن یا ترجمه؛ `exact=true` برای تطبیق لفظی |
| `quran_surahs` | ۱۱۴ سوره و تعداد آیات |
| `quran_surah_text` | بازهٔ آیات یک سوره، با سقف خروجی |
| `quran_ayah_translations` | ترجمه‌های یک آیه |
| `quran_ayah_commentary` | تفسیرهای یک آیه |
| `quran_ayah_hadiths` | احادیث مرتبط با یک آیه |
| `wikinoor_search` | جستجوی مقاله |
| `wikinoor_page` | متن مقاله و جعبهٔ اطلاعات |
| `qamus_search` | جستجوی واژه، اصطلاح یا نام |
| `qamus_word` | معنی کامل، ریشه، جمع و مثال |
| `qamus_dictionaries` | فهرست فرهنگ‌ها |
| `qamus_autocomplete` | پیشنهاد املا |
| `noordoc_search` | جستجوی پایان‌نامه |
| `noordoc_thesis` | چکیده و مشخصات |
| `noordoc_thesis_pages` | فهرست صفحات موجود |
| `tarikh_search` | جستجوی رویداد |
| `tarikh_event` | شرح رویداد و منابع گزارش |
| `tarikh_today` | رویدادهای امروز در تقویم قمری |

### استفاده

```bash
cd ~/MCP-noorlib
python3 -m venv .venv
.venv/bin/pip install noorlib_mcp-3.1.0-py3-none-any.whl
```

سه فرمان `noor-mcp`، `noorlib-mcp` و `arsh-alrahman` همان سرور را اجرا می‌کنند. در پیکربندی کلاینت MCP مسیر مطلق یکی از آن‌ها را بگذارید:

```json
{
  "mcpServers": {
    "noor": {
      "command": "/ABSOLUTE/PATH/MCP-noorlib/.venv/bin/noor-mcp",
      "env": {
        "NOORLIB_MCP_AUTH": "Bearer eyJ..."
      }
    }
  }
}
```

اگر توکن لازم نیست، کلید `env` را حذف کنید. پس از هر تغییر، کلاینت MCP را یک‌بار کاملاً ببندید و دوباره باز کنید.

مسیر معمول کار این است: جستجو، سپس شناسه، سپس متن. برای کتاب، `noorlib_search` و بعد `noorlib_book_info` و `noorlib_book_toc` و در نهایت `noorlib_book_page`. شمارهٔ صفحه داخل بخش شمرده می‌شود، نه در کل کتاب. `sectionNumber` را از فیلد `zone` در خروجی فهرست بردارید. وقتی متن کامل لازم نیست، `noorlib_search_in_book` اسنیپت را بدون کسر اعتبار برمی‌گرداند.

### اعتبار مطالعه در نور

جستجو، شناسنامه، فهرست و اسنیپت بدون ورود در دسترس است. متن کامل بعضی صفحه‌ها از اعتبار مطالعهٔ همان حساب کسر می‌شود. اگر اعتبار کافی نباشد، سرور پیام خود نور را برمی‌گرداند: «اعتبار کافی جهت کسر شارژ مطالعه صفحه وجود ندارد».

1. در [noorlib.ir](https://noorlib.ir) وارد حساب شوید.
2. در [افزایش اعتبار](https://noorlib.ir/package) یکی از اشتراک‌های یک‌ساله را بخرید. سهم مطالعه روی همان صفحه نوشته شده است: عادی ۱۵۰۰ صفحه، نقره‌ای ۴۵۰۰ صفحه، طلایی ۱۲۰۰۰ صفحه. پرداخت به همان حساب وصل می‌شود.
3. در همان مرورگر ابزار توسعه‌دهنده را باز کنید. در Chrome و Edge زبانهٔ Application، و در Firefox زبانهٔ Storage را انتخاب کنید. زیر Local Storage برای `https://noorlib.ir` مقدار `auth._token.inoor` را کپی کنید. این مقدار معمولاً با `Bearer eyJ` شروع می‌شود.
4. آن را در `NOORLIB_MCP_AUTH` بگذارید. اگر پیشوند `Bearer` را ننوشته باشید، سرور خودش اضافه می‌کند.
5. کلاینت MCP را کاملاً از نو راه‌اندازی کنید.

تا وقتی اشتراکی خریداری نشده باشد، موجودی صفر است و صفحهٔ مشمول اعتبار باز نمی‌شود. توکن را در گفتگو، مخزن یا تصویر منتشر نکنید. نام کاربری به‌تنهایی برای سرور کافی نیست.

پایان‌نامه‌ها در noordoc تا سطح چکیده و فهرست صفحات در دسترس‌اند. فایل صفحه و PDF از این سرور ارائه نمی‌شود. پایگاه‌های دیگر در مسیر معمولی این پروژه به توکن نیاز ندارند.

### متغیرهای محیطی

هر پایگاه پیشوند خودش را دارد: `NOORLIB_MCP_`، `HADITH_MCP_`، `QURAN_MCP_`، `WIKINOOR_MCP_`، `QAMUS_MCP_`، `NOORDOC_MCP_` و `TARIKH_MCP_`. کلیدهای مشترک `BASE_URL`، `TIMEOUT`، `THROTTLE` و `RETRIES` هستند.

| متغیر | پیش‌فرض | نقش |
|---|---|---|
| `NOORLIB_MCP_AUTH` | خالی | توکن حساب نور برای صفحه‌های مشمول اعتبار |
| `HADITH_MCP_AUTH` | خالی | توکن پایگاه حدیث؛ معمولاً لازم نیست |
| `NOORLIB_MCP_USE_PROXY` | `0` | `1` یعنی پروکسی سیستم استفاده شود. `NOOR_MCP_USE_PROXY` هم پذیرفته است |
| `NOORLIB_MCP_CA_BUNDLE` | خالی | مسیر بستهٔ گواهی سازمانی |
| `NOORLIB_MCP_UA` | عامل مرورگر | عامل کاربر دلخواه |
| `NOORLIB_MCP_LOG` | `INFO` | `DEBUG` برای گزارش مفصل |

پروکسی محیطی به‌طور پیش‌فرض نادیده گرفته می‌شود.

### شناسه‌های پرکاربرد

تمهید القواعد ۱۳۲۷ · شرح فصوص الحکم ۱۳۱۲ · نصوص الخصوص ۱۱۰۱۵ · کشف المراد ۱۲۳۶ · توضیح المراد ۱۱۹۸ · شوارق الإلهام ۱۴۱۵۹ · منشور جاودانه ۵۵۲۰۲ · نهج‌البلاغه ۳۵۴۲ · بحارالانوار ۲۵۶۴ · تجلیات الهیه ۱۲۲۷۶۲ · اسرار عرشیه ۱۲۲۷۶۰

الکافی، متن کامل هشت جلد: **۱۳۴۸** · نهج‌البلاغة: ۱۵۷۵ · ترجمهٔ اصول کافی: ۲۶۴۶ · الروضة من الکافی: ۲۶۴۲

### توسعه

```bash
pip install -e ".[dev]"
pytest
```

```
noorlib_mcp/
├── server.py
├── siteclient.py
├── client.py
├── hadith_client.py
├── quran_client.py
├── wikinoor_client.py
├── qamus_client.py
├── noordoc_client.py
├── tarikh_client.py
├── textutil.py
└── decoder.py
```

## English

One MCP server for the seven Noor-family databases. An agent can search, browse, and read text, translations, and commentary through a single connection.

| Site | Coverage | Tools |
|---|---|---|
| **noorlib.ir** | 109,000 books, 151,000 volumes | 6 `noorlib_*` |
| **hadith.inoor.ir** | 355+ hadith sources | 5 `hadith_*` |
| **quran.inoor.ir** | Text, 156 translations, 417 commentaries | 6 `quran_*` |
| **wikinoor.ir** | 33,000 bibliographic and biographical articles | 2 `wikinoor_*` |
| **qamus.inoor.ir** | 369,000 entries, 163 dictionaries | 4 `qamus_*` |
| **noordoc.ir** | 149,000 theses | 3 `noordoc_*` |
| **tarikh.inoor.ir** | Hundreds of thousands of events | 3 `tarikh_*` |

### Tools

| Tool | Purpose |
|---|---|
| `noorlib_search` | Search by title, author, or snippet |
| `noorlib_book_info` | Book metadata and access flags |
| `noorlib_book_toc` | Table of contents and per-section page ranges |
| `noorlib_book_page` | Readable text of one page, plus a scan image when present |
| `noorlib_search_in_book` | Snippets inside one book, with page and section |
| `noorlib_find_pages` | Pages containing the query |
| `hadith_search` | Search hadith text, with source, translation, and commentary filters |
| `hadith_by_id` | Full text, chain, book path, and the same hadith in other sources |
| `hadith_sources` | Source catalogue and `sourceId` |
| `hadith_toc` | Table of contents of one source |
| `hadith_related` | Similar hadiths |
| `quran_search` | Search the Arabic text or translations; `exact=true` for a literal match |
| `quran_surahs` | The 114 surahs and their verse counts |
| `quran_surah_text` | A verse range, with an output cap |
| `quran_ayah_translations` | Translations of one verse |
| `quran_ayah_commentary` | Commentaries on one verse |
| `quran_ayah_hadiths` | Hadiths related to one verse |
| `wikinoor_search` | Search articles |
| `wikinoor_page` | Article text and infobox |
| `qamus_search` | Search a word, term, or name |
| `qamus_word` | Full entry, root, plural, and examples |
| `qamus_dictionaries` | Dictionary catalogue |
| `qamus_autocomplete` | Spelling suggestions |
| `noordoc_search` | Search theses |
| `noordoc_thesis` | Abstract and record |
| `noordoc_thesis_pages` | Page inventory |
| `tarikh_search` | Search events |
| `tarikh_event` | Event description and cited sources |
| `tarikh_today` | Events for the current Hijri date |

### Use

```bash
cd ~/MCP-noorlib
python3 -m venv .venv
.venv/bin/pip install noorlib_mcp-3.1.0-py3-none-any.whl
```

`noor-mcp`, `noorlib-mcp`, and `arsh-alrahman` start the same server. Point the MCP client at the absolute path of one of them:

```json
{
  "mcpServers": {
    "noor": {
      "command": "/ABSOLUTE/PATH/MCP-noorlib/.venv/bin/noor-mcp",
      "env": {
        "NOORLIB_MCP_AUTH": "Bearer eyJ..."
      }
    }
  }
}
```

Omit `env` when no token is required. Restart the MCP client completely after any change.

The usual path is search, then an identifier, then the text. For a book: `noorlib_search`, `noorlib_book_info`, `noorlib_book_toc`, then `noorlib_book_page`. A page number counts inside its section, not across the book. Take `sectionNumber` from the `zone` field of the table of contents. `noorlib_search_in_book` returns snippets without spending study credit.

### Noor study credit

Search, metadata, tables of contents, and snippets do not require a sign-in. The full text of some pages is charged to the account’s study credit. When the balance is insufficient, the server returns Noor’s own message: «اعتبار کافی جهت کسر شارژ مطالعه صفحه وجود ندارد».

1. Sign in at [noorlib.ir](https://noorlib.ir).
2. Buy an annual plan on the [credit page](https://noorlib.ir/package). The page states the allowance: Standard 1,500 pages, Silver 4,500 pages, Gold 12,000 pages. The balance is attached to that account.
3. In the same browser, open the developer tools. Use Application in Chrome and Edge, or Storage in Firefox. Under Local Storage for `https://noorlib.ir`, copy `auth._token.inoor`. It usually begins with `Bearer eyJ`.
4. Set that value as `NOORLIB_MCP_AUTH`. The server adds the `Bearer` prefix when it is missing.
5. Restart the MCP client completely.

A valid token with an empty balance still cannot open a charged page. Do not publish the token in a chat, a repository, or a screenshot. A username alone is not accepted.

Noordoc exposes thesis metadata, abstracts, and page inventories. Page files and PDFs are not served. The other databases do not require a token on the flows this server documents.

### Environment

Each site has its own prefix: `NOORLIB_MCP_`, `HADITH_MCP_`, `QURAN_MCP_`, `WIKINOOR_MCP_`, `QAMUS_MCP_`, `NOORDOC_MCP_`, and `TARIKH_MCP_`. Shared keys are `BASE_URL`, `TIMEOUT`, `THROTTLE`, and `RETRIES`.

| Variable | Default | Role |
|---|---|---|
| `NOORLIB_MCP_AUTH` | empty | Noor account token for pages that spend study credit |
| `HADITH_MCP_AUTH` | empty | Hadith-site token; usually unnecessary |
| `NOORLIB_MCP_USE_PROXY` | `0` | `1` uses the system proxy. `NOOR_MCP_USE_PROXY` is also accepted |
| `NOORLIB_MCP_CA_BUNDLE` | empty | Corporate CA bundle |
| `NOORLIB_MCP_UA` | browser agent | Custom user agent |
| `NOORLIB_MCP_LOG` | `INFO` | `DEBUG` for a detailed log |

Ambient proxy variables are ignored unless the proxy option is turned on.

### Frequent identifiers

Tamhid al-Qawaid 1327 · Sharh Fusus al-Hikam 1312 · Nusus al-Khusus 11015 · Kashf al-Murad 1236 · Tawdih al-Murad 1198 · Shawariq al-Ilham 14159 · Manshur-i Javidana 55202 · Nahj al-Balagha 3542 · Bihar al-Anwar 2564 · Tajalliyat al-Ilahiyya 122762 · Asrar-i Arshiyya 122760

Al-Kafi, complete eight volumes: **1348** · Nahj al-Balagha: 1575 · translation of Usul al-Kafi: 2646 · al-Rawda min al-Kafi: 2642

### Development

```bash
pip install -e ".[dev]"
pytest
```

The package is one client per site, a shared HTTP core in `siteclient.py`, the MCP tools in `server.py`, and text cleanup in `textutil.py` and `decoder.py`.

## العربية

خادم MCP واحد لقواعد عائلة نور السبع. يصل الوكيل إلى البحث والفهرس والنص والترجمة والتفسير من اتصال واحد.

| الموقع | المحتوى | الأدوات |
|---|---|---|
| **noorlib.ir** | 109 آلاف كتاب و151 ألف مجلد | 6 أدوات `noorlib_*` |
| **hadith.inoor.ir** | أكثر من 355 مصدراً حديثياً | 5 أدوات `hadith_*` |
| **quran.inoor.ir** | النص و156 ترجمة و417 تفسيراً | 6 أدوات `quran_*` |
| **wikinoor.ir** | 33 ألف مقالة ببليوغرافية وسِيَرية | أداتان `wikinoor_*` |
| **qamus.inoor.ir** | 369 ألف مدخل و163 معجماً | 4 أدوات `qamus_*` |
| **noordoc.ir** | 149 ألف رسالة | 3 أدوات `noordoc_*` |
| **tarikh.inoor.ir** | مئات آلاف الأحداث | 3 أدوات `tarikh_*` |

### الأدوات

| الأداة | الوظيفة |
|---|---|
| `noorlib_search` | البحث بالعنوان أو المؤلف أو المقتطف |
| `noorlib_book_info` | بيانات الكتاب وحالة الإتاحة |
| `noorlib_book_toc` | الفهرس ونطاق صفحات كل قسم |
| `noorlib_book_page` | نص الصفحة بصيغة مقروءة، مع صورة المسح إن وُجدت |
| `noorlib_search_in_book` | مقتطفات داخل كتاب مع رقم الصفحة والقسم |
| `noorlib_find_pages` | الصفحات التي تحتوي عبارة البحث |
| `hadith_search` | البحث في الحديث مع تصفية المصدر والترجمة والشرح |
| `hadith_by_id` | النص والسند ومسار الكتاب ووروده في مصادر أخرى |
| `hadith_sources` | قائمة المصادر ومعرّف `sourceId` |
| `hadith_toc` | فهرس مصدر حديثي |
| `hadith_related` | الأحاديث المشابهة |
| `quran_search` | البحث في النص أو الترجمة؛ `exact=true` للتطابق اللفظي |
| `quran_surahs` | السور الـ 114 وعدد آياتها |
| `quran_surah_text` | نطاق آيات مع سقف للخرج |
| `quran_ayah_translations` | ترجمات آية |
| `quran_ayah_commentary` | تفاسير آية |
| `quran_ayah_hadiths` | أحاديث مرتبطة بآية |
| `wikinoor_search` | البحث في المقالات |
| `wikinoor_page` | نص المقال وصندوق المعلومات |
| `qamus_search` | البحث عن كلمة أو مصطلح أو اسم |
| `qamus_word` | المدخل الكامل مع الجذر والجمع والأمثلة |
| `qamus_dictionaries` | قائمة المعاجم |
| `qamus_autocomplete` | اقتراح الإملاء |
| `noordoc_search` | البحث في الرسائل |
| `noordoc_thesis` | الملخص والبيانات |
| `noordoc_thesis_pages` | جرد الصفحات |
| `tarikh_search` | البحث في الأحداث |
| `tarikh_event` | شرح الحدث ومصادره |
| `tarikh_today` | أحداث اليوم بالتقويم الهجري |

### الاستخدام

```bash
cd ~/MCP-noorlib
python3 -m venv .venv
.venv/bin/pip install noorlib_mcp-3.1.0-py3-none-any.whl
```

الأوامر `noor-mcp` و`noorlib-mcp` و`arsh-alrahman` تشغّل الخادم نفسه. ضع في إعداد عميل MCP المسار المطلق لأحدها:

```json
{
  "mcpServers": {
    "noor": {
      "command": "/ABSOLUTE/PATH/MCP-noorlib/.venv/bin/noor-mcp",
      "env": {
        "NOORLIB_MCP_AUTH": "Bearer eyJ..."
      }
    }
  }
}
```

احذف `env` إذا لم يكن الرمز مطلوباً. بعد أي تعديل، أغلق عميل MCP تماماً ثم افتحه من جديد.

المسار المعتاد هو البحث، ثم المعرّف، ثم النص. للكتاب: `noorlib_search` ثم `noorlib_book_info` ثم `noorlib_book_toc` ثم `noorlib_book_page`. يُحسب رقم الصفحة داخل القسم لا على مستوى الكتاب. خذ `sectionNumber` من الحقل `zone` في الفهرس. وتعيد `noorlib_search_in_book` المقتطفات من غير خصم رصيد.

### رصيد القراءة في نور

البحث وبيانات الكتاب والفهرس والمقتطفات لا تحتاج إلى دخول. النص الكامل لبعض الصفحات يُخصم من رصيد القراءة في الحساب. إذا لم يكفِ الرصيد، يعيد الخادم رسالة نور نفسها: «اعتبار کافی جهت کسر شارژ مطالعه صفحه وجود ندارد».

1. ادخل إلى حسابك في [noorlib.ir](https://noorlib.ir).
2. اشترِ أحد الاشتراكات السنوية من [صفحة الرصيد](https://noorlib.ir/package). الحصة مكتوبة في الصفحة نفسها: العادي ١٥٠٠ صفحة، والفضي ٤٥٠٠ صفحة، والذهبي ١٢٠٠٠ صفحة. الرصيد مرتبط بذلك الحساب.
3. في المتصفح نفسه افتح أدوات المطوّر. اختر Application في Chrome وEdge، أو Storage في Firefox. من Local Storage لـ `https://noorlib.ir` انسخ قيمة `auth._token.inoor`. تبدأ عادةً بـ `Bearer eyJ`.
4. ضعها في `NOORLIB_MCP_AUTH`. يضيف الخادم البادئة `Bearer` إذا غابت.
5. أعد تشغيل عميل MCP إغلاقاً كاملاً ثم فتحاً.

الرمز الصحيح مع رصيد صفري لا يفتح صفحة مخصومة. لا تنشر الرمز في محادثة أو مستودع أو لقطة شاشة. اسم المستخدم وحده لا يكفي.

تُتاح في noordoc بيانات الرسالة وملخصها وجرد صفحاتها. ملفات الصفحات وPDF غير متاحة من هذا الخادم. لا تحتاج قواعد البيانات الأخرى إلى رمز في المسارات الموثّقة هنا.

### متغيرات البيئة

لكل موقع بادئة: `NOORLIB_MCP_` و`HADITH_MCP_` و`QURAN_MCP_` و`WIKINOOR_MCP_` و`QAMUS_MCP_` و`NOORDOC_MCP_` و`TARIKH_MCP_`. المفاتيح المشتركة هي `BASE_URL` و`TIMEOUT` و`THROTTLE` و`RETRIES`.

| المتغير | الافتراضي | الدور |
|---|---|---|
| `NOORLIB_MCP_AUTH` | فارغ | رمز حساب نور للصفحات التي تستهلك رصيد القراءة |
| `HADITH_MCP_AUTH` | فارغ | رمز موقع الحديث؛ غالباً غير لازم |
| `NOORLIB_MCP_USE_PROXY` | `0` | `1` يستخدم بروكسي النظام. `NOOR_MCP_USE_PROXY` مقبول أيضاً |
| `NOORLIB_MCP_CA_BUNDLE` | فارغ | حزمة الشهادات المؤسسية |
| `NOORLIB_MCP_UA` | متصفح | وكيل مستخدم مخصص |
| `NOORLIB_MCP_LOG` | `INFO` | `DEBUG` لسجل مفصّل |

تُتجاهل متغيرات البروكسي ما لم يُفعَّل الخيار.

### معرّفات متكررة

تمهيد القواعد ١٣٢٧ · شرح فصوص الحكم ١٣١٢ · نصوص الخصوص ١١٠١٥ · كشف المراد ١٢٣٦ · توضيح المراد ١١٩٨ · شوارق الإلهام ١٤١٥٩ · منشور جاودانه ٥٥٢٠٢ · نهج البلاغة ٣٥٤٢ · بحار الأنوار ٢٥٦٤ · تجليات إلهية ١٢٢٧٦٢ · أسرار عرشية ١٢٢٧٦٠

الكافي، النص الكامل في ثمانية مجلدات: **١٣٤٨** · نهج البلاغة: ١٥٧٥ · ترجمة أصول الكافي: ٢٦٤٦ · الروضة من الكافي: ٢٦٤٢

### التطوير

```bash
pip install -e ".[dev]"
pytest
```

الحزمة عميل لكل موقع، ونواة HTTP مشتركة في `siteclient.py`، وأدوات MCP في `server.py`، وتنظيف النص في `textutil.py` و`decoder.py`.
