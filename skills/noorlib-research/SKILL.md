---
name: Noor Islamic text research
description: Researches the Quran, hadith, classical Islamic books, Arabic and Persian dictionaries, theses, and Hijri history through the noorlib-mcp server. Use when the user asks about a verse, hadith, tafsir, Islamic book, scholar, Arabic or Persian term, thesis, or historical event in the Noor libraries.
summary: Search seven Noor libraries, open the matching record, and answer with a quotation and a source link.
version: 1.0.0
tags: islam, quran, hadith, tafsir, arabic, persian, research
keywords: noorlib, quran, hadith, tafsir, islamic books, arabic dictionary, hijri history
use_cases: Find a Quran verse with translations and commentary; trace a hadith to its source; read a passage from a classical book; define an Arabic or Persian term; look up a thesis abstract or a Hijri historical event.
docs_url: https://github.com/alizare84/MCP-noorlib
---

# Noor Islamic text research

Requires: the noorlib-mcp MCP server from https://github.com/alizare84/MCP-noorlib

This skill is a research method. It does not contain the library texts. If the `noorlib_*`, `hadith_*`, `quran_*`, `wikinoor_*`, `qamus_*`, `noordoc_*`, or `tarikh_*` tools are missing, stop and ask the user to add this server, then wait:

```json
{
  "mcpServers": {
    "noor": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/alizare84/MCP-noorlib", "noor-mcp"]
    }
  }
}
```

`uv` must be installed. After the config change the user restarts the agent. Do not invent tool results and do not browse the web as a substitute for these libraries when the server is available.

## Which library

| The user wants | Start with |
|---|---|
| A book, author, or passage in the digital library | `noorlib_search` |
| A hadith, its chain, or which book it is in | `hadith_search` |
| A Quran verse, translation, or commentary | `quran_search` or `quran_surah_text` |
| A scholar, book, or bibliographic article | `wikinoor_search` |
| A word, root, plural, or technical term | `qamus_search` |
| A thesis or dissertation | `noordoc_search` |
| A historical event or what happened on a Hijri date | `tarikh_search` or `tarikh_today` |

Search in the language of the source. Arabic and Persian queries both work. If a name may be misspelled, call `qamus_autocomplete` before `qamus_search`.

## How to read a book

1. `noorlib_search` with the title, author, or phrase. Keep `bookId`.
2. `noorlib_book_info` for the record, volumes, and whether the text is free to read.
3. When the user needs a passage, call `noorlib_search_in_book` first. It returns snippets and does not spend reading credit.
4. Open `noorlib_book_toc` and read `zone`. Page numbers count inside that section, not across the whole book. Pass `sectionNumber` from `zone` to `noorlib_book_page`.
5. Call `noorlib_book_page` only for the page the user actually needs.

Some full pages debit the user's Noor reading balance. Search, the book record, the table of contents, and snippets do not. If a page returns that the balance is empty, say so and give the snippet plus the book link. Do not ask the user to paste a token into the chat, and do not read tokens from the browser. The user sets `NOORLIB_MCP_AUTH` in their own MCP config if they want charged pages.

## How to answer

Quote the tool text. Name the work, the author when the tool gives one, and the location it gives: surah and ayah, hadith source and id, book title with page and section, or the event id. Put the library link next to the quotation.

Do not present a paraphrase as a quotation. If several records match, list the closest ones and open only the one that fits. If nothing matches, say the libraries returned no record.

Thesis pages from noordoc stop at the abstract and the page inventory. Do not claim a thesis PDF was retrieved. Hadith, Quran, dictionary, wiki, and history calls normally need no account.

Keep each answer to the passage asked for. A verse means the Arabic text, one or two translations if requested, and commentary only when the user asked for tafsir.
