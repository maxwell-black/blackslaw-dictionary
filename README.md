# Black's Law Dictionary (1910)

A free, searchable web version of Black's Law Dictionary, Second Edition (1910) by Henry Campbell Black, M.A.

## Live Site

**https://blackslaw.io**

## About

This project provides free access to 12,941 legal definitions from the classic 1910 edition of Black's Law Dictionary. The corpus was rebuilt from the Internet Archive's DjVu XML extraction, with an editorial overlay system for entry classification, AI-assisted OCR cleanup (Claude Haiku 4.5 and Claude Sonnet 4.6), and LexPredict gap recovery.

### Features

- Fast search across all entries by term or definition content
- Browse by letter with quick A-Z navigation
- Cross-reference links between related legal terms
- Source page links to the Internet Archive scan
- Mobile-friendly, dark mode, adjustable font size
- Static site, no server required

## Technical

- **Frontend**: Vanilla HTML, CSS, JavaScript
- **Data**: 12,941 entries in split-file JSON (data/manifest.json + per-letter files)
- **Hosting**: GitHub Pages with custom domain
- **Source**: [Internet Archive DjVu XML](https://archive.org/details/blacks-law-dictionary-2nd-edition-1910)
- **Pipeline**: editorial_overlay.json + body_corrections.json -> generate_live_corpus_v3.py -> validate_rebuild.py -> split_entries.py

## Data Source

The raw text was sourced from the Internet Archive's digitization of Black's Law Dictionary, 2nd Edition (1910). The DjVu XML scan (93 MB, 1,328 leaves) was processed through word-level bounding box parsing, two-column page separation, and entry boundary detection. OCR artifacts were cleaned through deterministic pattern matching and AI-assisted review.

## Deployment

Push to main branch deploys automatically via GitHub Pages.

## License

The original Black's Law Dictionary (2nd Edition, 1910) is in the **public domain**.

This web implementation is released under the MIT License.

## Credits

- **Original Author**: Henry Campbell Black, M.A. (1910)
- **Digitization**: Internet Archive
- **Web Edition**: Maxwell Black
- **Rebuild Pipeline**: Claude Code (Anthropic)
- A small number of entries were recovered from LexPredict's independent extraction (CC-BY-SA 4.0).

---

*Free legal knowledge for everyone.*

## Revision history (auto)

<!-- REVISION_HISTORY:START -->
<!-- REVISION_HISTORY:END -->
