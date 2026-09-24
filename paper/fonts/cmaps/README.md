# Chinese PDF text mapping

`Adobe-GB1-UCS2` is Adobe's standard CID-to-Unicode mapping for the Adobe GB1
collection used by Fandol Song/Hei. Its original copyright and permissive
redistribution terms are preserved in the file header.

Primary source: <https://github.com/adobe-type-tools/mapping-resources-pdf/blob/master/pdf2unicode/Adobe-GB1-UCS2>
Included version: 9.000, copyright 1990–2020 Adobe, from the installed Poppler
CMap resource. This file is not a font, and does not change the page's glyphs,
positions or figure styling.

Some xdvipdfmx versions omit `/ToUnicode` for standard CJK character collections.
The resulting PDF relies on external reader CMaps; several text parsers decode
the CID values as unrelated Unicode characters instead. `scripts/pdf_quality.py`
adds this map only to unmapped Adobe/GB1 fonts with Identity-H/V encoding, then
requires embedded fonts and readable Chinese on every page before publication.
Unknown encodings fail clearly. Existing valid maps are preserved.
