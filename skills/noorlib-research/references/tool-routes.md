# Tool routes

Use the first tool in the row, then the later ones only with an id that an earlier call returned.

| Library | Search | Open one record | Read text |
|---|---|---|---|
| noorlib.ir books | `noorlib_search` | `noorlib_book_info`, `noorlib_book_toc` | `noorlib_search_in_book`, then `noorlib_book_page` |
| hadith.inoor.ir | `hadith_search`, `hadith_sources` | `hadith_by_id`, `hadith_toc` | `hadith_related` |
| quran.inoor.ir | `quran_search`, `quran_surahs` | `quran_surah_text` | `quran_ayah_translations`, `quran_ayah_commentary`, `quran_ayah_hadiths` |
| wikinoor.ir | `wikinoor_search` | `wikinoor_page` | |
| qamus.inoor.ir | `qamus_autocomplete`, `qamus_search`, `qamus_dictionaries` | `qamus_word` | |
| noordoc.ir | `noordoc_search` | `noordoc_thesis` | `noordoc_thesis_pages` lists pages only |
| tarikh.inoor.ir | `tarikh_search`, `tarikh_today` | `tarikh_event` | |

`quran_search` takes `exact=true` for a literal match. Book page numbers come from the table-of-contents `zone`, and they count inside that section.
