# Black's Law Dictionary (1910)

A free, searchable web version of Black's Law Dictionary, Second Edition (1910) by Henry Campbell Black, M.A.

## Live Site

**https://blackslaw.io**

## About

This project provides free access to 13,009 legal definitions from the classic 1910 edition of Black's Law Dictionary. The corpus was rebuilt from the Internet Archive's DjVu XML extraction, cross-validated against a legacy OCR corpus, and editorially reviewed through a multi-phase overlay system that classifies all 13,641 original entries.

### Features

- Fast search across all entries by term or definition content
- Browse by letter with quick A-Z navigation
- Cross-reference links between related legal terms
- Source page links to the Internet Archive scan
- Mobile-friendly, dark mode, adjustable font size
- Static site, no server required

## Technical

- **Frontend**: Vanilla HTML, CSS, JavaScript
- **Data**: 13,009 entries in JSON format (split by letter for lazy loading)
- **Hosting**: GitHub Pages with custom domain
- **Source**: [Internet Archive DjVu](https://archive.org/details/blacks-law-dictionary-2nd-edition-1910)
- **Pipeline**: Editorial overlay -> live corpus generator -> validator -> split

### Entry types in live corpus

| Type | Count | Description |
|------|-------|-------------|
| verified_main | 10,513 | DjVu source-backed, high confidence |
| provisional_main | 320 | DjVu source-backed, moderate confidence |
| recovered_main | 160 | Recovered from source pages |
| headword_corrected | 9 | OCR headword fixes (e.g., ACOESS -> ACCESS) |
| legacy_retained | ~1,800 | Legacy OCR bodies, pending DjVu recovery |
| subentry | ~200 | Sub-entries linked to parent terms |
| alias_variant | 15 | Spelling variants with redirects |

## Data Source

The raw text was sourced from the Internet Archive's digitization of Black's Law Dictionary, 2nd Edition (1910). The DjVu XML extraction was processed through a multi-stage pipeline: page segmentation, headword extraction, body assembly, source alignment, and editorial overlay classification.

## License

The original Black's Law Dictionary (2nd Edition, 1910) is in the **public domain**.

This web implementation is released under the MIT License.

## Credits

- **Original Author**: Henry Campbell Black, M.A. (1910)
- **Digitization**: Internet Archive
- **Rebuild Pipeline**: Claude Code (Anthropic)

---

*Free legal knowledge for everyone.*

## Revision history (auto)

<!-- REVISION_HISTORY:START -->
<!-- REVISION_HISTORY:END -->
