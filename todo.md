# Todo

- Add search/filter to the Rewatch view. Filtering only removes films from the due list and keeps the algorithm's order; it reuses the Library's filter registry (`views/library/filters.ts`, FR-EXT-05) rather than building a second mechanism (FUTURE_WORK "Rewatch list filtering").
- Extend the search/filter by genre (FR-SF-07): a film matches if any of its genres is one of the selected ones (case-insensitive exact match).
- Extend the filter by tags (FR-SF-06): a film has to carry every selected tag to appear.
- Extend the filter by director (FR-SF-02): free-text, case-insensitive substring match.
- Extend the filter by release year (FR-SF-08): a from–to year range.
- Let several filters apply at once (FR-SF-03): every active criterion is ANDed, with the count (FR-SF-05) and the single clear action (FR-SF-04) covering all of them.
- Extend the filter with logical operators (AND, OR, NOT) between criteria. This goes beyond FR-SF-03, which specifies AND only, so the requirements doc needs an update alongside it.
