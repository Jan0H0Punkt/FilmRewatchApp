# Requirements Document — Film Tracker Web Application

**Version:** 1.1  
**Status:** Approved  
**Created:** 2026-05-15  
**Last updated:** 2026-06-05  
**Companion to:** [DESIGN_V1.md](../designs/DESIGN_V1.md) · [FUTURE_WORK_V1.md](./FUTURE_WORK_V1.md) · [OPEN_DECISIONS_V1.md](./OPEN_DECISIONS_V1.md)  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [User & Context](#2-user--context)
3. [Architectural Principles](#3-architectural-principles)
4. [Data Model](#4-data-model)
5. [Functional Requirements](#5-functional-requirements)
   - 5.1 [Film Library Management](#51-film-library-management)
   - 5.2 [Rating System](#52-rating-system)
   - 5.3 [Tagging](#53-tagging)
   - 5.4 [Search & Filter](#54-search--filter)
   - 5.5 [Rewatch Suggestion Engine](#55-rewatch-suggestion-engine)
   - 5.6 [Offline & Sync](#56-offline--sync)
6. [Extensibility Requirements](#6-extensibility-requirements)
7. [UI / UX Requirements](#7-ui--ux-requirements)
   - 7.1 [Rewatch Suggestion View](#71-rewatch-suggestion-view)
   - 7.2 [Search & Filter View](#72-search--filter-view)
   - 7.3 [Film Detail View](#73-film-detail-view)
   - 7.4 [Responsive Design](#74-responsive-design)
8. [Non-Functional Requirements](#8-non-functional-requirements)

---

## 1. Project Overview

### 1.1 Purpose

The Film Tracker is a personal web application that allows a single user to catalog films they have watched, rate them over time, organise
them with tags, and discover films worth rewatching through an algorithmic suggestion engine.

### 1.2 Goals

- Provide a fast, low-friction way to log a watched film and record an initial rating.
- Maintain a full rating history per film so that opinions tracked over multiple watches are preserved and averaged.
- Allow flexible organisation of films via free-form tags.
- Surface rewatch candidates through a dedicated, algorithmically driven view.

### 1.3 Scope

The following capabilities are **in scope**:

- Creating, viewing, editing, and deleting film records.
- Recording and browsing a per-film rating history; computing the average rating.
- Assigning and removing tags on films.
- Searching and filtering the full film library.
- Displaying algorithmically generated rewatch suggestions in a card-based view.
- Responsive layout for desktop and mobile browsers.
- Offline-capable frontend: browsing and viewing cached data remain functional without a network connection; operations that cannot be
  answered from cache surface a neutral, non-blocking "currently unavailable" message (see FR-OFF-04) rather than failing silently.
- Write operations performed while offline are queued locally and synced to the backend when connectivity is restored.
- Single local deployment: the backend and database run on the user's laptop; the mobile browser syncs only when the device is on the same
  network and the laptop is running.

The following are explicitly **out of scope** for this version:

- User authentication and multi-user support.
- Integration with external film databases or metadata APIs.
- Always-on / remote-server deployment and multi-topology hosting (the application targets a single local-laptop deployment; see §3.6).
- Social or sharing features.
- Native mobile applications (iOS / Android).
- Export or import of data.

---

## 2. User & Context

### 2.1 User Profile

The application has exactly **one user**. There is no registration, login, or session management. The application is personal and private by
nature of deployment; no access control layer is required at the application level.

### 2.2 Usage Context

- Primarily used on a **desktop browser** for data entry and browsing.
- Also used on a **mobile browser** for quick lookups, logging films, and browsing rewatch suggestions — including when the backend is
  temporarily unreachable (e.g. the laptop is off or the device is not on the local network).
- The user is technically proficient and does not require guided onboarding flows.
- The typical local deployment scenario is: backend runs on the user's laptop; the mobile device syncs data whenever it is on the same Wi-Fi
  network as the laptop and the backend is running. The frontend must remain fully functional when this connectivity is absent.

---

## 3. Architectural Principles

These principles are not optional design preferences — they are binding constraints on how the system must be structured. They exist to
ensure the application can grow incrementally without requiring structural rewrites.

### 3.1 Layered Architecture

The system shall be implemented in clearly separated, independently testable layers:

- **Presentation layer** — responsible solely for rendering UI and handling user input. Contains no business logic and no direct data
  access.
- **Business logic layer** — responsible for all domain rules (validation, average rating computation, duplicate detection, rewatch
  scoring). Has no knowledge of how data is stored or how the UI is rendered.
- **Data access layer** — responsible solely for reading and writing data. Exposes a stable interface to the business logic layer; its
  internal implementation (database engine, ORM, file storage) can be changed without affecting other layers.

No layer shall directly call into a non-adjacent layer (e.g. the presentation layer shall never query the database directly).

### 3.2 API-First Backend

- The backend shall expose all functionality through a **versioned HTTP API** (e.g. `/api/v1/`).
- No view, feature, or client shall access data through any mechanism other than this API.
- The API contract (endpoints, request/response schemas, error formats) shall be explicitly documented (e.g. via OpenAPI / Swagger).
- API versioning shall be in place from day one (`/api/v1/`) so that breaking changes in the future can be introduced under a new version
  without disrupting existing consumers.

### 3.3 Isolated Algorithm Module

- The rewatch suggestion algorithm shall reside in its own **isolated, self-contained module** within the application codebase.
- This module shall have no dependencies on the UI layer or the data access layer. It receives a pure data payload and returns a result (see
  FR-RW-01 – FR-RW-03).
- Modifying or replacing the algorithm shall require changes only inside this module.

### 3.4 Integration Adapter Pattern

- Any future external data integration (e.g. a film metadata lookup API such as TMDB) shall be implemented as a **dedicated adapter** — an
  isolated module that translates external API responses into the application's internal data model.
- The core film creation and editing logic shall not be modified to accommodate an external integration. The adapter is additive only.
- Adapters shall be optional and switchable; the application must function fully without any adapter being active.

### 3.5 Configuration over Code

- Environment-specific values (API base URLs, external service keys, feature flags) shall be managed through external configuration (e.g.
  environment variables), not hardcoded in application logic.
- Feature flags shall be usable to enable or disable new or experimental features at configuration time without a code deployment.

### 3.6 Single Local Deployment

- The application targets a **single deployment**: the backend and database run on the user's laptop. Always-on remote-server hosting and
  multi-topology switching are out of scope for this version.
- The frontend is configured with the backend's base URL when the client is built. Pointing it at a different backend is a build/config
  change, not a source-code change.
- The backend shall not embed or hard-code any client origin URLs; CORS / allowed-origin rules shall be configurable.

### 3.7 Cache-First Client with Offline Write Queue

- The frontend shall treat the **backend as its authoritative data source** when reachable. A local cache (e.g. IndexedDB) acts as a
  read-through cache and as the data source of last resort when the backend is unreachable.
- All reads shall be attempted against the backend first. Successful responses shall populate the local cache. When the backend is
  unreachable, reads shall be served transparently from the local cache; the user shall not be shown any indicator that a fallback has
  occurred.
- If a read operation cannot be fulfilled from the cache while the backend is also unreachable, the UI shall present a neutral, non-blocking
  "currently unavailable" message. The message shall not name connectivity, the cache, the backend, or sync as the cause. It shall never
  silently return an empty or incorrect result.
- Write operations shall always appear to the user as immediately successful. When the backend is reachable, writes are sent directly to it
  and the cache is updated on success. When the backend is unreachable, writes are committed to the local cache and added to a persistent
  sync queue. This distinction shall be entirely invisible to the user.
- The sync and caching layer shall be a clearly isolated module, separate from the business logic and UI layers, so that its implementation
  can be replaced (e.g. switching sync strategy) without affecting other parts of the system.

---

## 4. Data Model

### 4.1 Film

A Film is the central entity of the application. Each film record represents one unique motion picture as perceived by the user (i.e. the
same film can only exist once in the library).

| Field            | Type                | Required           | Constraints                                | Description                                                                                              |
| ---------------- | ------------------- | ------------------ | ------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `id`             | UUID                | Yes (system)       | Unique, immutable                          | System-generated surrogate identifier (used for joins, foreign keys, and references)                     |
| `natural_key`    | String              | Yes (system)       | Unique; derived                            | System-generated key for duplicate detection and sync deduplication; see note below                      |
| `titles`         | List\<Title\>       | Yes                | 1–∞ titles; exactly one primary            | All titles for the film (main + alternatives); see the Title Object below                                |
| `release_year`   | Integer             | Yes                | 1888–current year                          | Year the film was first released                                                                         |
| `director`       | String              | Yes                | 1–255 characters; anyUnicode(any language) | Name of the director(s)                                                                                  |
| `genre`          | List\<Genre\>       | Yes                | 1–∞ genres                                 | Genres assigned to the film; at least one is required. Free text, not an enum; see the Genre entity (§4.4) |
| `poster_image`   | URL                 | No                 | Valid URL; max 2048 characters             | URL pointing to a poster image; entered by the user                                                      |
| `tags`           | List\<Tag\>         | Yes                | 1–∞ tags                                   | User-defined tags assigned to this film; at least one is required                                        |
| `is_favorite`    | Boolean             | Yes                | Default `false`                            | Whether the user has marked this film as a favourite                                                     |
| `delay_days`     | Integer             | Yes                | ≥ 0; default `0`                           | User-set delay (in days) to defer the next rewatch suggestion; passed as a hint to the rewatch algorithm |
| `rating_history` | List\<RatingEntry\> | Yes (≥ 1)          | At least one entry                         | Ordered list of all ratings given to this film; never empty (every film has been watched at least once)  |
| `average_rating` | Decimal (computed)  | —                  | 0.5–5.0; 1 decimal place                   | Arithmetic mean of all `RatingEntry.value` values; always present (history is never empty)               |
| `created_at`     | ISO 8601 DateTime   | Yes (system)       | Immutable                                  | Timestamp when the film record was created                                                               |
| `updated_at`     | ISO 8601 DateTime   | Yes (system)       | —                                          | Timestamp of the last modification to any field                                                          |

> **Note:** The `natural_key` is composed as `lowercase(trim(primary_title))\|release_year\|lowercase(trim(director))`, where
> `primary_title` is the `value` of the film's primary title. It is system-generated, never entered or edited by the user, and is used for
> duplicate detection and sync deduplication.

#### Title Object

A Film has one or more **titles**, stored in the `titles` list. Each entry is a Title object:

| Field         | Type    | Required | Constraints                                  | Description                                                                            |
| ------------- | ------- | -------- | -------------------------------------------- | -------------------------------------------------------------------------------------- |
| `value`       | String  | Yes      | 1–255 characters; any Unicode (any language) | The title text                                                                         |
| `is_primary`  | Boolean | Yes      | Exactly one title per film is `true`         | Marks the main title — shown by default in the UI and used to derive the `natural_key` |
| `is_original` | Boolean | Yes      | At most one title per film is `true`         | Marks the film's original-language title (optional)                                    |

Title rules:

- Every Film has **at least one** Title; films with no title are not permitted.
- **Exactly one** Title per Film has `is_primary = true` — the main title displayed by default throughout the UI.
- If a Film has exactly one Title, that Title is automatically the primary one; the user cannot unset it.
- When a Film has multiple Titles, the user chooses which one is primary and may change that choice at any time.
- **At most one** Title per Film has `is_original = true` — the original-language title. Marking a title as original is optional and is
  controlled entirely by the user.
- A single Title may be both primary and original (e.g. a film entered only under its original-language title).
- Title text accepts any Unicode characters, so titles in any language or script can be entered.
- The `natural_key` (and therefore duplicate detection) is derived from the **primary title**. Editing the primary title's `value`, or
  designating a different title as primary, changes the `natural_key` (see FR-LIB-08, FR-LIB-09).

### 4.2 RatingEntry

A RatingEntry represents a single rating event — one instance of the user consciously rating or re-rating a film.

| Field        | Type              | Required     | Constraints                | Description                                                  |
| ------------ | ----------------- | ------------ | -------------------------- | ------------------------------------------------------------ |
| `id`         | UUID              | Yes (system) | Unique, immutable          | System-generated identifier                                  |
| `film_id`    | UUID              | Yes          | Foreign key → Film         | The film this rating belongs to                              |
| `value`      | Decimal           | Yes          | 0.5–5.0; increments of 0.5 | The rating value given                                       |
| `watch_date` | ISO 8601 Date     | Yes          | Not in the future          | The date on which the film was watched for this rating event |
| `created_at` | ISO 8601 DateTime | Yes (system) | Immutable                  | Timestamp when this rating entry was recorded                |

> **Note:** `watch_date` represents *when the film was watched*, which may differ from *when the rating was entered* into the system. Both
> are stored separately.

### 4.3 Tag

A Tag is a user-defined label used to categorise films.

| Field        | Type              | Required     | Constraints                                | Description                              |
| ------------ | ----------------- | ------------ | ------------------------------------------ | ---------------------------------------- |
| `id`         | UUID              | Yes (system) | Unique, immutable                          | System-generated identifier              |
| `name`       | String            | Yes          | 1–50 characters; unique (case-insensitive) | The tag label                            |
| `created_at` | ISO 8601 DateTime | Yes (system) | Immutable                                  | Timestamp when the tag was first created |

> **Note:** A Tag cannot exist independently of films. Every Tag must be assigned to at least one Film at all times; a Tag that would
> otherwise have no film associations is automatically deleted (see FR-TAG-04 and Section 4.5).

### 4.4 Genre

A Genre is a free-text label describing a film's genre. Genres are modelled **identically to Tags**: a Genre is a shared entity, created
implicitly when a film is saved, deduplicated by name, and automatically removed when no film references it.

| Field        | Type              | Required     | Constraints                                 | Description                                |
| ------------ | ----------------- | ------------ | ------------------------------------------- | ------------------------------------------ |
| `id`         | UUID              | Yes (system) | Unique, immutable                           | System-generated identifier                |
| `name`       | String            | Yes          | 1–100 characters; unique (case-insensitive) | The genre label (free text, not an enum)   |
| `created_at` | ISO 8601 DateTime | Yes (system) | Immutable                                   | Timestamp when the genre was first created |

> **Note:** Like a Tag, a Genre cannot exist independently of films. Every Genre must be assigned to at least one Film; a Genre left with no
> film associations is automatically deleted. Genres are created implicitly while assigning them to a film (never as standalone entities),
> are unique case-insensitively, and support autocomplete — mirroring the Tag rules (§5.3).

### 4.5 Entity Relationships

```
Film  1      ──── 1..*   RatingEntry
Film  1..*   ──── 1..*   Tag
Film  1..*   ──── 1..*   Genre
```

- A Film has **one or more** RatingEntries — never zero (the library holds only watched films; see FR-LIB-03). A RatingEntry belongs to
  exactly one Film.
- A Film must have **at least one** Tag, and a Tag must be assigned to **at least one** Film (many-to-many); orphan (unused) tags are not
  permitted. **Genres follow the same many-to-many rule**, with the same orphan-deletion behaviour.
- Deleting a Film cascades to delete all its associated RatingEntries. Tag and genre associations are also removed; any Tag or Genre left
  with no remaining Film associations is automatically deleted.

---

## 5. Functional Requirements

### 5.1 Film Library Management

#### 5.1.1 Create Film

- **FR-LIB-01:** The user shall be able to create a new film record. The following are mandatory at creation: at least one `title`,
  `release_year`, `director`, at least one `genre`, and at least one `tag`. If only one title is provided it becomes the primary title
  automatically; if several are provided the user designates which one is primary. The user may optionally mark one title as the
  original-language title (see Section 4.1, Title Object).
- **FR-LIB-02:** Several fields are not required input at creation time: `poster_image` is optional and may be omitted entirely;
  `is_favorite` and `delay_days` are not asked for in the create form and are defaulted by the system to `false` and `0` respectively. All
  three can be set or changed later through edit.
- **FR-LIB-03:** The library holds **only films the user has actually watched**, so the first `RatingEntry` is **mandatory** at creation: a
  film is created together with its first rating in one operation (the "log a watched film" flow). Every film therefore always has at least
  one rating (see also FR-RAT-07 and FR-RAT-11).
- **FR-LIB-04:** Upon creation, `created_at` and `updated_at` shall be set automatically by the system to the current UTC timestamp, and
  `natural_key` shall be derived automatically from the film's primary title, `release_year`, and `director` (see Section 4.1). The user
  shall never enter or see the `natural_key` directly.
- **FR-LIB-05:** The system shall not permit the creation of duplicate films. Two films are duplicates when they share the same
  `natural_key` — the same primary title, `release_year`, and `director` (case-insensitive, whitespace-trimmed; see Section 4.1). The
  duplicate check shall run in the background as the user fills in the create form. If the film being created would duplicate an existing
  film, creation shall be **blocked**: the system shall inform the user which existing film it matches and offer to open that film instead.
  The user cannot override the block to create a duplicate.

#### 5.1.2 Edit Film

- **FR-LIB-06:** The user shall be able to edit any user-editable field of a film record (`titles`, `release_year`, `director`, `genre`,
  `poster_image`, `tags`, `is_favorite`, `delay_days`). Editing `titles` includes adding/removing titles and changing which title is marked
  primary or original, subject to the Title rules in Section 4.1.
- **FR-LIB-07:** `id` and `created_at` shall never be editable.
- **FR-LIB-08:** Upon any successful edit, `updated_at` shall be updated to the current UTC timestamp. If the primary title (its `value` or
  which title is primary), `release_year`, or `director` changed, `natural_key` shall be recomputed.
- **FR-LIB-09:** Duplicate detection (FR-LIB-05) shall also apply when editing a film's primary title, `release_year`, or `director`. If an
  edit would make the film duplicate another existing film, the edit shall be **blocked** and shall not be applied; the system shall inform
  the user which existing film it would collide with. The user may instead choose to merge the two films (see Section 5.1.5).

#### 5.1.3 Delete Film

- **FR-LIB-10:** The user shall be able to delete a film record.
- **FR-LIB-11:** Deleting a film shall require an explicit confirmation step before the operation is executed (e.g. a confirmation dialog).
- **FR-LIB-12:** Deletion shall cascade: all associated `RatingEntry` records are permanently deleted. Tag and genre associations are also
  removed; any Tag or Genre left with no remaining Film associations is automatically deleted (consistent with FR-TAG-04 and Section 4.5).

#### 5.1.4 Poster Image

- **FR-LIB-13:** The user shall be able to set a poster image by entering a URL.
- **FR-LIB-14:** The system shall validate that the entered value is a well-formed URL (max 2048 characters). No format or file-type
  validation is performed; the user is responsible for providing a URL that resolves to an image.
- **FR-LIB-15:** The user shall be able to remove a previously set poster URL, reverting the film to a poster-less state.
- **FR-LIB-16:** When no poster URL is set, the UI shall display a neutral placeholder.

#### 5.1.5 Merge Films

- **FR-LIB-17:** When duplicate detection blocks an edit (FR-LIB-09), the system shall offer the user the option to **merge** the two
  duplicate films into a single film record. Films may be merged only when they are duplicates of each other; there is no standalone merge
  action.
- **FR-LIB-18:** A merge shall combine the two films as follows:
  - **Collection fields** — `titles`, `tags`, `rating_history`, and `genre` — shall be combined as the **union** of both films' entries,
    with duplicate entries removed.
  - **Single-value fields** whose values differ between the two films (e.g. `poster_image`) shall be resolved by an explicit user choice:
    the user selects which film's value to keep.
  - Fields that are identical by definition of a duplicate (primary title, `release_year`, `director`) are carried over unchanged.
- **FR-LIB-19:** The **older** of the two records (earlier `created_at`) shall survive the merge: its `id` and `created_at` are retained.
  The other record shall be deleted. `updated_at` shall be set to the time of the merge. The `natural_key` is unchanged, as both films
  already share it.
- **FR-LIB-20:** After the `titles` union, the merged film must still satisfy the Title rules (Section 4.1): exactly one primary title (the
  shared primary title is retained as primary) and at most one original title. If the two films designated different original titles, the
  user shall choose which one — or neither — is marked original.
- **FR-LIB-21:** A merge shall require explicit user confirmation and shall be presented to the user as irreversible. Until the user
  confirms, neither film is modified.

---

### 5.2 Rating System

#### 5.2.1 Add a Rating

- **FR-RAT-01:** The user shall be able to add a new `RatingEntry` to any film at any time, representing a new watch event.
- **FR-RAT-02:** A `RatingEntry` requires a `value` (0.5–5.0, in increments of 0.5) and a `watch_date`.
- **FR-RAT-03:** The `watch_date` shall not be settable to a future date. The system shall reject future dates with a validation error.
- **FR-RAT-04:** Multiple `RatingEntry` records for the same film on the same `watch_date` are permitted (the user may have genuinely
  re-rated on the same day).

#### 5.2.2 Rating History

- **FR-RAT-05:** The full `RatingEntry` history of a film shall be viewable, ordered by `watch_date` descending (most recent first).
- **FR-RAT-06:** Each entry in the history view shall display: `value`, `watch_date`, and `created_at`.
- **FR-RAT-07:** The user shall be able to delete a specific `RatingEntry` from the history. Deletion shall require confirmation. Because a
  film must always have at least one rating (FR-LIB-03), deleting a film's **last** remaining rating deletes the **whole film** — the
  confirmation shall make this clear (it names the film, not just the rating). (To correct a film's only rating, add the corrected entry
  first, then delete the wrong one.)
- **FR-RAT-08:** The user shall **not** be able to edit the `value` or `watch_date` of an existing `RatingEntry`. To correct an entry, they
  must delete it and create a new one.

#### 5.2.3 Average Rating

- **FR-RAT-09:** The system shall compute `average_rating` as the arithmetic mean of all `RatingEntry.value` values for that film, rounded
  to one decimal place.
- **FR-RAT-10:** The `average_rating` shall be recomputed automatically whenever a `RatingEntry` is added or deleted.
- **FR-RAT-11:** Every film has at least one rating (FR-LIB-03), so `average_rating` is always a real value — there is no "not yet rated" or
  empty-history state, and it shall never be displayed as zero.

---

### 5.3 Tagging

- **FR-TAG-01:** The user shall be able to create a new tag by typing a tag name while assigning tags to a film. A tag is always created in
  the context of being assigned to a film; tags cannot be created as standalone, unassigned entities.
- **FR-TAG-02:** Tag names shall be unique in a case-insensitive manner. The system shall prevent creation of a tag whose name matches an
  existing tag when compared case-insensitively.
- **FR-TAG-03:** The user shall be able to assign one or more existing tags to a film.
- **FR-TAG-04:** The user shall be able to remove a tag from a film. If, after removal, the tag is no longer assigned to any film, the
  system shall automatically delete the now-orphaned tag. Tags still assigned to other films are unaffected.
- **FR-TAG-05** *(deferred to a later version)***:** Global tag delete — removing a tag from all films in one action — is **out of scope for
  this version**: it requires a management/settings screen the three-view UI does not include. Tags still disappear through the per-film
  removal + orphan-cleanup path (FR-TAG-04).
- **FR-TAG-06:** The tag input on a film shall support autocomplete, suggesting existing tags as the user types.

**Genres** behave **identically to tags** (see the Genre entity, §4.4): they are created implicitly while assigning them to a film, are
unique case-insensitively (FR-TAG-02 analogue), are automatically deleted when no film references them (FR-TAG-04 analogue), and support
autocomplete (FR-TAG-06 analogue). At least one genre is required per film (FR-LIB-01). Global genre delete is deferred for the same reason
as global tag delete (FR-TAG-05).

---

### 5.4 Search & Filter

Search and filtering shall be built so capabilities can be added incrementally (see FR-EXT-05). For the **initial version, only search by
film name and director are required**; every other dimension is optional and may be added later.

#### 5.4.1 Required (initial version)

- **FR-SF-01:** The user shall be able to search films by **title (film name)** using a free-text search. The search shall match against
  **all** of a film's titles (primary and alternative), be case-insensitive, and match substrings (e.g. searching "god" matches "The
  Godfather"; searching a film's original-language title also matches it).
- **FR-SF-02:** The user shall be able to search films by **director** using a free-text search (case-insensitive, substring match).
- **FR-SF-03:** All active search and filter criteria shall be applied together using **AND logic** — a film must satisfy every active
  criterion to appear in the results. (Initially this covers title and director; it shall extend to any optional dimension added later.)
- **FR-SF-04:** The user shall be able to clear all active search/filter criteria with a single action.
- **FR-SF-05:** The total count of films matching the current criteria shall always be visible.

#### 5.4.2 Optional (may be added incrementally)

The following are desirable but **not required** for the initial version. Each shall be addable by extending the search/filter configuration
without redesigning the view (see FR-EXT-05):

- **FR-SF-06:** Filter films by one or more **tags** (AND logic: a film must have all selected tags to appear).
- **FR-SF-07:** Filter films by **genre** — a film matches if any of its genres is one of the selected genres (case-insensitive, exact match
  per genre).
- **FR-SF-08:** Filter films by **release year** (range: from year / to year).
- **FR-SF-09:** Filter films by **average rating** (minimum threshold, e.g. "only show films rated 3.5 or above").
- **FR-SF-10:** Sort the results by fields such as primary `title` (A–Z, Z–A), `release_year` (asc/desc), `average_rating` (asc/desc), or
  `watch_date` of the most recent RatingEntry (asc/desc).
- **FR-SF-11:** Reflect the active search/filter/sort state in the URL (query parameters) so the view can be bookmarked and shared.

---

### 5.5 Rewatch Suggestion Engine

#### 5.5.1 Algorithm Contract

The rewatch suggestion feature is powered by an external algorithm supplied by the user. This section defines the contract that the
application must honour when integrating it.

- **FR-RW-01:** The application shall invoke the rewatch algorithm as a **pure function** with a well-defined input payload and consume its
  output to render the suggestion view. The algorithm's internal logic is outside the scope of this document.
- **FR-RW-02:** The application shall pass the following data to the algorithm for every film in the library:

| Input Field         | Source                                          | Description                                                                                            |
| ------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `film_id`           | Film.id                                         | Unique identifier                                                                                      |
| `average_rating`    | Computed                                        | Arithmetic mean of all rating entries (always present — every film has ≥ 1 rating)                     |
| `watch_count`       | Computed (length of `rating_history`)           | Number of times the film has been watched (number of `RatingEntry` records); always ≥ 1               |
| `last_watched_date` | Computed (max `watch_date` in `rating_history`) | Date of the most recent watch (always present)                                                        |
| `is_favorite`       | Film.is_favorite                                | Whether the user has marked this film as a favourite                                                   |
| `delay_days`        | Film.delay_days                                 | User-set delay before the next rewatch suggestion                                                      |

- **FR-RW-03:** The algorithm shall return an **ordered list of currently-due films only**. Each object in the list must contain at minimum:

| Output Field              | Type    | Description                                                                                                                                                                  |
| ------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `film_id`                 | UUID    | Identifies which film the suggestion is for                                                                                                                                |
| `days_until_next_rewatch` | Integer | Days relative to today: `0` = due today, a **negative** value = overdue by that many days. Only films with a value `≤ 0` (due or overdue) are returned; not-yet-due films are omitted. |

- **FR-RW-04:** The algorithm shall return the list ordered ascending by `days_until_next_rewatch` — the **most overdue** (most negative)
  first, down to those just becoming due (`0`). The application shall not re-sort this order. (The view may *filter* the list to a subset
  without re-sorting; see §7.1.)
- **FR-RW-05:** The algorithm runs on the backend as a **once-daily scheduled job**; its result is stored and served to the client, which
  caches it. An up-to-one-day lag is accepted: a film that becomes newly due purely by the passage of time appears at the next daily run, and
  changes to `delay_days` / `is_favorite` take effect at the next run. The one exception is handled immediately on the client — a film the
  user has just watched is removed from the displayed list at once, without waiting for the next run.
- **FR-RW-06:** If the algorithm returns an empty list (e.g. no films qualify), the view shall display an appropriate empty state message.
- **FR-RW-07:** If the algorithm throws an error or times out, the view shall display a non-blocking error message. The rest of the
  application shall remain fully functional.

---

### 5.6 Offline & Sync

#### 5.6.1 Offline Availability

- **FR-OFF-01:** All three views (Rewatch Suggestion, Search & Filter, Film Detail) shall remain usable when the backend is unreachable,
  displaying data from the local cache. The user shall not see any indication that data is being served from the cache rather than the
  backend; the fallback shall be transparent.
- **FR-OFF-02:** The application shall be installable as a **Progressive Web App (PWA)** on mobile devices, enabling home-screen access and
  offline operation without requiring a native app.
- **FR-OFF-03:** On first load (when online), the application shall cache all film, rating, and tag **metadata** locally so that subsequent
  offline sessions have access to the full library. Poster images are referenced as URLs (not stored as binaries in the data cache); their
  offline availability relies on the browser's HTTP / service-worker cache on a best-effort basis and is not guaranteed.
- **FR-OFF-04:** Read operations shall degrade gracefully when the requested data cannot be fulfilled (i.e. it is not in the cache and the
  backend is unreachable). In that case the UI shall present a neutral, non-blocking "currently unavailable" message — never a blank state
  or a silent empty result. The message shall not name connectivity, the cache, the backend, or sync as the cause.

#### 5.6.2 Offline Writes & Sync Queue

- **FR-OFF-05:** Write operations (create film, edit film, delete film, add rating, delete rating, create tag, assign/remove tag) performed
  **while online** shall be sent directly to the backend; the local cache shall be updated on success. If an online attempt fails
  transiently (network unreachable mid-request, timeout, server 5xx), the write shall fall back to the offline path (see NFR-REL-01) — it
  is committed to the local cache and added to the sync queue, silently and without surfacing an error. Write operations performed **while
  offline** shall be committed to the local cache immediately and added to a **persistent sync queue**.
- **FR-OFF-06:** The sync queue shall survive app restarts, tab closures, and device reboots. The queue is an internal background mechanism:
  the user shall not be able to view, edit, reorder, or discard pending writes. A pending write is only removed once it has been
  successfully synced to the backend (or definitively rejected by the backend per FR-OFF-10).
- **FR-OFF-07:** When connectivity to the backend is restored, the application shall automatically process the sync queue in the order
  operations were originally performed (FIFO).
- **FR-OFF-08:** Each sync queue entry shall record: the operation type, the full payload, and the UTC timestamp of the original local
  write.

#### 5.6.3 Conflict Resolution

- **FR-OFF-09:** Because the application has a single user, true multi-party write conflicts are not expected. The conflict resolution
  strategy shall be **last-write-wins by `updated_at` timestamp**: the record with the later `updated_at` value is authoritative.
- **FR-OFF-10:** If the backend definitively rejects a queued operation during sync (e.g. the record was deleted on another device before
  the queue was processed), the application shall surface a non-blocking notification to the user explaining that a specific change could
  not be saved. The notification shall not reference sync, the queue, the backend, or connectivity; it shall describe the affected
  film/rating/tag and the failed action in user-level terms only. The failure shall not be silently discarded.
- **FR-OFF-11:** After a successful sync, the local cache shall be updated to reflect the authoritative backend state, resolving any
  divergence.

#### 5.6.4 Connectivity Handling

- **FR-OFF-12:** The application shall not display any connectivity status — no online, offline, or syncing indicator, persistent or
  transient. The user shall not see any cue, label, icon, or message that reveals whether the backend is reachable.
- **FR-OFF-13:** Pending writes shall not be surfaced to the user (consistent with FR-OFF-06). The application shall not display a queue
  length, a "pending sync" count, or any similar status. Sync is a silent background process.
- **FR-OFF-14:** The application shall attempt to drain the sync queue **automatically**, with no user action required, whenever any of the
  following occurs:
  - The browser's `online` event fires (network reconnection detected).
  - The application becomes visible or focused (tab focus, PWA returning to foreground).
  - Any backend request succeeds after one or more recent failures (opportunistic piggyback).
- **FR-OFF-15:** There shall be no user-facing "Sync now" or similar manual sync action. The user shall not need to be aware that a sync
  mechanism exists.

---

## 6. Extensibility Requirements

These requirements ensure the application can accommodate new features, views, and integrations without requiring structural rework of
existing components.

### 6.1 New Views

- **FR-EXT-01:** Adding a new view to the application shall not require changes to the data access layer or the business logic layer.
- **FR-EXT-02:** The navigation structure shall be designed so that new entries can be added to it without modifying existing navigation
  items.
- **FR-EXT-03:** Shared UI components (cards, rating display, tag chips, etc.) shall be implemented as reusable, self-contained components
  so that new views can compose them without duplication.

### 6.2 New Film Fields

- **FR-EXT-04:** Adding a new optional field to the Film entity shall require changes only in the data model, the API schema, and the
  relevant UI form. No other layer shall require modification.
- **FR-EXT-05:** The Search & Filter feature shall be designed so that new filterable fields can be added by extending the filter
  configuration, not by rewriting the filter component.

### 6.3 External API Integration

- **FR-EXT-06:** The application shall be designed so that an external film metadata API (e.g. TMDB) can be integrated as an **optional
  lookup step** during film creation, without modifying the existing manual entry flow.
- **FR-EXT-07:** The integration point for such an adapter shall be explicitly defined in the film creation flow (e.g. a designated "search
  external source" action that pre-fills the form). The form submission and persistence logic shall remain unchanged regardless of whether
  the adapter is active.
- **FR-EXT-08:** It shall be possible to add, remove, or swap an external API adapter purely through configuration and the addition of a new
  adapter module — without touching core business logic.

### 6.4 Algorithm Extensibility

- **FR-EXT-09:** The rewatch algorithm module shall expose a single, documented function signature. Replacing or updating the algorithm
  shall require only modifying the contents of that module, with no changes to the calling code.
- **FR-EXT-10:** Additional scoring or suggestion algorithms (e.g. "films similar to ones I rated highly") shall be addable as separate
  modules following the same contract, selectable via configuration.

### 6.5 API Extensibility

- **FR-EXT-11:** New API endpoints shall follow the established versioned URL structure and the documented request/response conventions,
  ensuring consistency across the growing API surface.
- **FR-EXT-12:** The API shall be designed so that a future additional client (e.g. a mobile native app, a CLI tool) can consume it without
  requiring backend changes.

### 6.6 Deployment & Sync Strategy

- **FR-EXT-13** *(out of scope for this version)***:** Multi-topology deployment — switching between local-laptop and always-on-server
  hosting through configuration — is out of scope; this version targets a single local-laptop deployment (§3.6). The backend stays free of
  hard-coded client origins so a future revision could revisit this without a rewrite.
- **FR-EXT-14:** The sync module shall be isolated behind a stable interface so that its internal strategy (e.g. batching, retry/backoff
  policy, or conflict-resolution details) can be changed by swapping the module implementation, with no changes required in the UI or
  business logic layers. Real-time/push-based sync (e.g. WebSockets) is explicitly **not** a goal — the single-user model does not justify
  it.

---

## 7. UI / UX Requirements

The application consists of exactly **three views**. Navigation between views shall be possible at all times via a persistent navigation
element — a **navigation drawer** on desktop and a **bottom navigation bar** on mobile (see §7.4).

---

### 7.1 Rewatch Suggestion View

**Purpose:** The primary discovery view — presents algorithmically ranked films the user should consider rewatching.

**Layout:**

- Displayed as a **responsive card grid**.
- The view shows **only currently-due films** (FR-RW-03), ordered strictly by the algorithm's output — **most overdue first**, down to those
  just becoming due. The client does not re-sort the list (it may filter it to a subset).

**Film Card — Required Elements:**

| Element             | Source                                    | Notes                                                         |
| ------------------- | ----------------------------------------- | ------------------------------------------------------------- |
| Poster image        | Film.poster_image                         | Displays placeholder if no image is set                       |
| Title               | Film primary title                        | Truncated with ellipsis if too long for the card width        |
| Release year        | Film.release_year                         |                                                               |
| Average rating      | Film.average_rating                       | Displayed as a star or numeric representation                 |
| Rewatch status      | RewatchSuggestion.days_until_next_rewatch | "Due now" when `0`; "Overdue by N days" when negative (only due/overdue films are shown) |
| Favourite indicator | Film.is_favorite                          | Visual marker (e.g. star/heart icon) shown only when `true`   |

**Interactions:**

- Clicking/tapping a card navigates to the **Film Detail View** for that film.
- The suggestion list updates **automatically** (when the view opens and on reconnect); there is no manual refresh action.
- The view shall display a loading indicator while the suggestion list is being fetched.
- An **empty state** is shown when no suggestions are returned (FR-RW-06).
- An **error state** is shown if the algorithm fails (FR-RW-07), without hiding the cards from the previous successful run.

---

### 7.2 Search & Filter View

**Purpose:** Allows the user to browse the complete film library and narrow it down through search and filters.

**Search & Filtering:**

> The concrete layout, controls, and visual design of search and filtering are **intentionally left open** at this stage. This is an area to
> be researched and designed carefully later. What follows specifies *what* the user can search and filter by, and that the mechanism must
> be easy to extend — not *how* it is laid out or which controls are used.

- For the initial version, the view shall let the user search the full library by two **required** dimensions (functional detail in FR-SF-01
  – FR-SF-05):
  - Film title (free-text, across all of a film's titles).
  - Director (free-text).
- The following dimensions are **optional** and may be added incrementally (FR-SF-06 – FR-SF-11): tags, genre, release year, minimum average
  rating, sorting, and bookmarkable URL state.
- The view shall always support clearing all active search/filter criteria at once and showing how many films currently match.
- The search/filter mechanism shall be built for **extensibility** (see FR-EXT-05): it shall be possible to start with a minimal subset of
  the above and add further searchable/filterable dimensions over time by extending a configuration/registry, without redesigning the view.
- The presentation of the results (list, grid, or other) is not prescribed.

**Film Result Item — Required Elements:**

| Element                  | Source              |
| ------------------------ | ------------------- |
| Poster image (thumbnail) | Film.poster_image   |
| Title                    | Film primary title  |
| Release year             | Film.release_year   |
| Director                 | Film.director       |
| Genre                    | Film.genre          |
| Average rating           | Film.average_rating |
| Tags                     | Film.tags           |

**Interactions:**

- Clicking/tapping a result item navigates to the **Film Detail View**.
- A clearly visible **"Add Film"** action (e.g. floating button or top-bar button) opens the Add Film form. The form's fields, validation,
  and duplicate handling are defined by the data model (§4.1) and the Create Film requirements (§5.1.1, FR-LIB-01–05) and are not restated
  here. On successful save, the new film appears in the result list.
- Search and filter results update without a full page reload (the exact responsiveness — live, debounced, or on submit — is part of the
  search/filter UX to be designed later).
- The user shall be able to tell which search/filter criteria are currently active. How this is surfaced is left to the later UX design.

---

### 7.3 Film Detail View

**Purpose:** The full record for a single film — all metadata, the complete rating history, and edit/delete controls.

**Layout — two logical sections:**

#### Section A: Film Metadata

| Element                      | Notes                                                                                                                                                                                                                              |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Poster image (large)         | Full-size display rendered from the stored URL; URL set/edit/remove controls visible in edit mode (see FR-LIB-13–FR-LIB-16)                                                                                                        |
| Titles                       | Primary title shown prominently; any alternative titles listed beneath it (original-language title indicated). Editable via edit form                                                                                              |
| Release year                 |                                                                                                                                                                                                                                    |
| Director                     |                                                                                                                                                                                                                                    |
| Genre                        | Displayed as a list (a film may have multiple genres)                                                                                                                                                                              |
| Tags                         | Displayed as chips; add/remove tags directly from this view                                                                                                                                                                        |
| Favourite                    | Toggle reflecting `Film.is_favorite`; user can switch it directly from this view or via the Edit form                                                                                                                              |
| Rewatch delay                | Reflects `Film.delay_days` (days the next rewatch suggestion is deferred; `0` means none). Editable inline or via the Edit form                                                                                                    |
| Average rating               | **Read-only** display. Computed from `rating_history` (see FR-RAT-09 / FR-RAT-10); cannot be edited directly — to change it, add or delete rating entries in Section B. Visually distinguished (e.g. large star rating component). |
| Created / updated timestamps | **Read-only** display (system-managed); shown in a subdued style                                                                                                                                                                   |


- An **Edit** button opens the **user-editable** metadata fields (titles, release year, director, genre, poster image, tags, `is_favorite`,
  `delay_days`) for editing in place or in a modal. Computed and system-managed fields (`average_rating`, `created_at`, `updated_at`) are
  display-only and are not part of the edit form.
- A **Delete Film** button triggers a confirmation dialog (FR-LIB-11) before deletion. After deletion, the user is navigated back to the
  Search & Filter View.

#### Section B: Rating History

- Displayed as a **chronological list**, most recent entry first.
- Each entry shows: `value` (as stars or numeric), `watch_date`, `created_at`.
- Each entry has a **Delete** action with confirmation (FR-RAT-07).
- An **"Add Rating"** action (button) opens an inline form or modal with: `value` (star picker, 0.5–5.0 in 0.5 increments) and `watch_date`
  (date picker, no future dates).
- The rating history is never empty — a film always has at least one rating (FR-LIB-03) — so no empty-history state is needed. Deleting the
  last remaining rating deletes the film (FR-RAT-07).

---

### 7.4 Responsive Design

- The application shall be fully usable across the range of common viewport sizes — from small mobile phones up to large desktop monitors.
  Specific viewport breakpoints and the exact supported range are part of the responsive design work and shall be decided then.
- All interactive elements (buttons, inputs, cards) shall have touch targets sized to be reliably tappable on mobile devices, in line with
  current accessibility guidance (see NFR-A11Y-01, WCAG 2.1 AA). The exact minimum size shall be chosen as part of the responsive/UX design
  work.
- Typography, spacing, and layout shall adapt fluidly between breakpoints. No horizontal scrolling shall occur on any view at any supported
  viewport width.
- The navigation element shall adapt between a **navigation drawer** (desktop) and a **bottom navigation bar** (mobile).
- Images shall be responsive and never cause layout overflow.

---

## 8. Non-Functional Requirements

### 8.1 Performance

Performance targets are **intentionally not specified at this stage**. The expected library size and feature scope are modest enough that
performance is not anticipated to be a concern. Concrete targets (page load, navigation responsiveness, search latency, library size limits)
may be added later once real usage patterns are observable. Until then, the only commitment is that the application shall remain usable in
normal use.

### 8.2 Data Persistence

- **NFR-DATA-01:** All film, rating, and tag data shall be persisted in a server-side data store as the authoritative record. Data must
  survive browser refreshes, tab closures, and device changes once synced.
- **NFR-DATA-02:** The frontend shall maintain a **local persistent cache** (e.g. IndexedDB) populated by backend responses. This cache
  serves as the read source when the backend is unreachable and additionally holds any unsynced pending writes from offline sessions.
- **NFR-DATA-03:** Write operations performed while online shall be sent directly to the backend; if an online attempt fails transiently,
  the write falls back to the local cache + sync queue (see FR-OFF-05, NFR-REL-01). Write operations performed while offline shall be
  committed to the local cache immediately and added to the sync queue. From the user's perspective, all paths shall appear identically as
  an immediately successful save; the application shall not expose the distinction.

### 8.3 Data Integrity

- **NFR-INT-01:** `average_rating` shall always reflect the current state of `rating_history`. There shall be no scenario in which a stale
  average is displayed.
- **NFR-INT-02:** Deleting a film shall atomically delete all its associated `RatingEntry` records. Partial deletions are not acceptable.
- **NFR-INT-03:** All user inputs shall be validated on both the client side (immediate feedback) and the server side (authoritative
  enforcement).

### 8.4 Browser Support

- **NFR-BROWSER-01:** The application shall be fully functional in the **two most recent stable releases** of the following browsers: Google
  Chrome, Mozilla Firefox, Apple Safari, Microsoft Edge.
- **NFR-BROWSER-02:** The application shall not rely on any browser-specific APIs that are not available across all four target browsers.

### 8.5 Accessibility

- **NFR-A11Y-01:** The application shall meet **WCAG 2.1 Level AA** compliance.
- **NFR-A11Y-02:** All interactive elements shall be keyboard-navigable.
- **NFR-A11Y-03:** All images shall have descriptive `alt` text; poster images shall use the film's primary title as alt text.
- **NFR-A11Y-04:** Colour shall not be the sole means of conveying information (e.g. rating values must also be conveyed numerically or via
  accessible labels).

### 8.6 Reliability

- **NFR-REL-01:** User input from write operations shall never be silently discarded. Transient or network-level failures during an online
  write attempt (the backend being briefly unreachable, a timeout, a 5xx) shall be handled internally by committing to the local cache and
  adding the write to the sync queue (per §5.6.2) — they shall not surface to the user as errors and shall not reveal connectivity state
  (consistent with FR-OFF-12). The only user-facing write-failure path is the definitive backend rejection covered by FR-OFF-10.
- **NFR-REL-02:** The application shall handle the rewatch algorithm failing gracefully without crashing or blocking other functionality
  (FR-RW-07).

### 8.7 Maintainability

- **NFR-MAINT-01:** All API endpoints shall be documented in an OpenAPI / Swagger specification, kept up to date as endpoints are added or
  changed.
- **NFR-MAINT-02:** Business logic shall not reside in UI components, API route handlers, or database queries. It shall live exclusively in
  the business logic layer (see Section 3.1).
- **NFR-MAINT-03:** All error responses from the API shall follow a single, consistent error schema (e.g. `{ "error": { "code": "...",
  "message": "..." } }`). No endpoint shall invent its own error format.
- **NFR-MAINT-04:** Environment-specific configuration (database URLs, external API keys, ports) shall never be hardcoded. All such values
  shall be read from environment variables or a configuration file that is excluded from version control.
- **NFR-MAINT-05:** The codebase shall include a top-level README that documents how to run the application locally, how to run tests, and
  where to find the API documentation.

### 8.8 Offline & Sync

- **NFR-OFF-01:** The application shall achieve a **Lighthouse PWA score of 90 or above**, confirming installability, service worker
  registration, and offline capability.
- **NFR-OFF-02:** The service worker shall cache all static application assets (HTML, CSS, JS, fonts, icons) on first install, so the
  application shell loads instantly without a network request on subsequent visits.
- **NFR-OFF-03:** The local data cache shall be able to hold the full film library without artificial item-count limits. Read performance
  characteristics of the cache are not formally specified at this stage (see §8.1).
- **NFR-OFF-04:** The sync queue shall be persisted in a durable local store (e.g. IndexedDB). It shall not be held in memory alone; entries
  must survive a full browser or device restart.
- **NFR-OFF-05:** Sync processing shall be **idempotent**: if the same queued operation is submitted to the backend more than once (e.g. due
  to a network timeout where the first attempt actually succeeded), the backend shall produce the same result without creating duplicate
  records or returning an unrecoverable error.
- **NFR-OFF-06:** The frontend's backend base URL shall be a single configurable value, set when the client is built. This version targets
  one local-laptop deployment (§3.6); runtime topology switching is out of scope (FR-EXT-13).

---

## Revision History

| Version | Date       | Summary                                                                                                                                  |
| ------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 1.0     | 2026-05-15 | Initial requirements (Draft).                                                                                                           |
| 1.1     | 2026-06-05 | Reconciled with DESIGN_V1 and approved. Genre is now a first-class entity (§4.4, modelled like Tag). Watched-only library: every film must have ≥ 1 rating — first rating mandatory at create, deleting the last rating deletes the film, no "not yet rated" state (FR-LIB-03, FR-RAT-07/11, §4.1, §4.5, §7.3). Rewatch engine is a once-daily backend job returning only due/overdue films, most-overdue first; no manual refresh (FR-RW-02/03/04/05, §7.1). Navigation is a desktop drawer + mobile bottom bar (§7, §7.4). Deployment narrowed to a single local-laptop target; multi-topology / deployment-agnostic dropped (§1.3, §3.6, FR-EXT-13, NFR-OFF-06). Global tag/genre delete deferred (FR-TAG-05). |

---
