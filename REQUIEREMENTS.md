# Requirements Document — Film Tracker Web Application

**Version:** 1.0  
**Date:** 2026-05-15  
**Status:** Draft  

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

The Film Tracker is a personal web application that allows a single user to catalog films they have watched, rate them over time, organise them with tags, and discover films worth rewatching through an algorithmic suggestion engine.

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
- Offline-capable frontend: all views are usable without a network connection using locally cached data.
- Optimistic local writes with background sync to the backend when connectivity is restored.
- Deployment-agnostic architecture: the application shall run without code changes in at least the following deployment topologies:
  - **Local laptop** — backend runs on the user's laptop; mobile browser syncs only when the device is on the same network and the laptop is running.
  - **Always-on server** — backend runs on a remotely hosted server, always reachable.

The following are explicitly **out of scope** for this version:

- User authentication and multi-user support.
- Integration with external film databases or metadata APIs.
- Social or sharing features.
- Native mobile applications (iOS / Android).
- Export or import of data.

---

## 2. User & Context

### 2.1 User Profile

The application has exactly **one user**. There is no registration, login, or session management. The application is personal and private by nature of deployment; no access control layer is required at the application level.

### 2.2 Usage Context

- Primarily used on a **desktop browser** for data entry and browsing.
- Also used on a **mobile browser** for quick lookups, logging films, and browsing rewatch suggestions — including when the backend is temporarily unreachable (e.g. the laptop is off or the device is not on the local network).
- The user is technically proficient and does not require guided onboarding flows.
- The typical local deployment scenario is: backend runs on the user's laptop; the mobile device syncs data whenever it is on the same Wi-Fi network as the laptop and the backend is running. The frontend must remain fully functional when this connectivity is absent.

---

## 3. Architectural Principles

These principles are not optional design preferences — they are binding constraints on how the system must be structured. They exist to ensure the application can grow incrementally without requiring structural rewrites.

### 3.1 Layered Architecture

The system shall be implemented in clearly separated, independently testable layers:

- **Presentation layer** — responsible solely for rendering UI and handling user input. Contains no business logic and no direct data access.
- **Business logic layer** — responsible for all domain rules (validation, average rating computation, duplicate detection, rewatch scoring). Has no knowledge of how data is stored or how the UI is rendered.
- **Data access layer** — responsible solely for reading and writing data. Exposes a stable interface to the business logic layer; its internal implementation (database engine, ORM, file storage) can be changed without affecting other layers.

No layer shall directly call into a non-adjacent layer (e.g. the presentation layer shall never query the database directly).

### 3.2 API-First Backend

- The backend shall expose all functionality through a **versioned HTTP API** (e.g. `/api/v1/`).
- No view, feature, or client shall access data through any mechanism other than this API.
- The API contract (endpoints, request/response schemas, error formats) shall be explicitly documented (e.g. via OpenAPI / Swagger).
- API versioning shall be in place from day one (`/api/v1/`) so that breaking changes in the future can be introduced under a new version without disrupting existing consumers.

### 3.3 Isolated Algorithm Module

- The rewatch suggestion algorithm shall reside in its own **isolated, self-contained module** within the application codebase.
- This module shall have no dependencies on the UI layer or the data access layer. It receives a pure data payload and returns a result (see FR-RW-01 – FR-RW-03).
- Modifying or replacing the algorithm shall require changes only inside this module.

### 3.4 Integration Adapter Pattern

- Any future external data integration (e.g. a film metadata lookup API such as TMDB) shall be implemented as a **dedicated adapter** — an isolated module that translates external API responses into the application's internal data model.
- The core film creation and editing logic shall not be modified to accommodate an external integration. The adapter is additive only.
- Adapters shall be optional and switchable; the application must function fully without any adapter being active.

### 3.5 Configuration over Code

- Environment-specific values (API base URLs, external service keys, feature flags) shall be managed through external configuration (e.g. environment variables), not hardcoded in application logic.
- Feature flags shall be usable to enable or disable new or experimental features at configuration time without a code deployment.

### 3.6 Deployment-Agnostic Design

- The application shall make **no assumptions** about the network topology between the frontend and the backend. The backend's base URL shall be the only required configuration value for the frontend.
- Switching between deployment topologies (local laptop, always-on remote server, or any other hosting arrangement) shall require only a change to this configuration value — no code changes in either the frontend or the backend.
- The backend shall not embed or hard-code any client origin URLs. CORS and network access rules shall be fully configurable.

### 3.7 Offline-First Client

- The frontend shall follow an **offline-first** architecture: it operates against a local data store (e.g. IndexedDB via a service worker) as its primary data source, and treats the backend as a sync target rather than a prerequisite.
- All reads (browsing, searching, viewing details) shall be served from the local store, regardless of backend reachability.
- All writes (create, edit, delete) shall be committed to the local store immediately and queued for sync to the backend. The user shall never be blocked from writing data due to a missing backend connection.
- The sync layer shall be a clearly isolated module, separate from the business logic and UI layers, so that its implementation can be replaced (e.g. switching sync strategy) without affecting other parts of the system.

---

## 4. Data Model

### 4.1 Film

A Film is the central entity of the application. Each film record represents one unique motion picture as perceived by the user (i.e. the same film can only exist once in the library).

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `id` | UUID | Yes (system) | Unique, immutable | System-generated identifier |
| `title` | String | Yes | 1–255 characters | The film's title |
| `release_year` | Integer | Yes | 1888–current year | Year the film was first released |
| `director` | String | No | 1–255 characters | Name of the director(s) |
| `genre` | String | No | 1–100 characters | Primary genre (free text, not an enum) |
| `poster_image` | Binary / URL | No | Max 5 MB; JPEG, PNG, or WebP | Cover image uploaded by the user |
| `tags` | List\<Tag\> | No | 0–∞ tags | User-defined tags assigned to this film |
| `rating_history` | List\<RatingEntry\> | Yes (can be empty) | — | Ordered list of all ratings given to this film |
| `average_rating` | Decimal (computed) | — | 0.5–5.0; 1 decimal place | Computed as the arithmetic mean of all `RatingEntry.value` values; `null` if history is empty |
| `created_at` | ISO 8601 DateTime | Yes (system) | Immutable | Timestamp when the film record was created |
| `updated_at` | ISO 8601 DateTime | Yes (system) | — | Timestamp of the last modification to any field |

### 4.2 RatingEntry

A RatingEntry represents a single rating event — one instance of the user consciously rating or re-rating a film.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `id` | UUID | Yes (system) | Unique, immutable | System-generated identifier |
| `film_id` | UUID | Yes | Foreign key → Film | The film this rating belongs to |
| `value` | Decimal | Yes | 0.5–5.0; increments of 0.5 | The rating value given |
| `watch_date` | ISO 8601 Date | Yes | Not in the future | The date on which the film was watched for this rating event |
| `created_at` | ISO 8601 DateTime | Yes (system) | Immutable | Timestamp when this rating entry was recorded |

> **Note:** `watch_date` represents *when the film was watched*, which may differ from *when the rating was entered* into the system. Both are stored separately.

### 4.3 Tag

A Tag is a user-defined label used to categorise films.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `id` | UUID | Yes (system) | Unique, immutable | System-generated identifier |
| `name` | String | Yes | 1–50 characters; unique (case-insensitive) | The tag label |
| `created_at` | ISO 8601 DateTime | Yes (system) | Immutable | Timestamp when the tag was first created |

### 4.4 Entity Relationships

```
Film  1 ──── * RatingEntry
Film  * ──── * Tag
```

- A Film can have zero or more RatingEntries. A RatingEntry belongs to exactly one Film.
- A Film can have zero or more Tags. A Tag can be assigned to zero or more Films (many-to-many).
- Deleting a Film cascades to delete all its associated RatingEntries. Tag associations are also removed; the Tag entity itself is not deleted.

---

## 5. Functional Requirements

### 5.1 Film Library Management

#### 5.1.1 Create Film

- **FR-LIB-01:** The user shall be able to create a new film record by providing at minimum a `title` and `release_year`.
- **FR-LIB-02:** All other fields (`director`, `genre`, `poster_image`, `tags`) shall be optional at creation time.
- **FR-LIB-03:** The first `RatingEntry` may optionally be created together with the film in the same operation (combined "log a watched film" flow).
- **FR-LIB-04:** Upon creation, `created_at` and `updated_at` shall be set automatically by the system to the current UTC timestamp.
- **FR-LIB-05:** The system shall prevent duplicate films. Two films are considered duplicates if they share the same `title` (case-insensitive) **and** the same `release_year`. The system shall warn the user and require explicit confirmation to proceed if a duplicate is detected.

#### 5.1.2 Edit Film

- **FR-LIB-06:** The user shall be able to edit any user-editable field of a film record (`title`, `release_year`, `director`, `genre`, `poster_image`, `tags`).
- **FR-LIB-07:** `id` and `created_at` shall never be editable.
- **FR-LIB-08:** Upon any successful edit, `updated_at` shall be updated to the current UTC timestamp.
- **FR-LIB-09:** The duplicate-detection rule (FR-LIB-05) shall also apply when editing a film's `title` or `release_year`.

#### 5.1.3 Delete Film

- **FR-LIB-10:** The user shall be able to delete a film record.
- **FR-LIB-11:** Deleting a film shall require an explicit confirmation step before the operation is executed (e.g. a confirmation dialog).
- **FR-LIB-12:** Deletion shall cascade: all associated `RatingEntry` records are permanently deleted. Associated tags (the Tag entities themselves) are not deleted.

#### 5.1.4 Poster Image

- **FR-LIB-13:** The user shall be able to upload a poster image from their local device.
- **FR-LIB-14:** Accepted formats are JPEG, PNG, and WebP.
- **FR-LIB-15:** The maximum file size is 5 MB. The system shall reject uploads exceeding this limit with a clear error message.
- **FR-LIB-16:** The user shall be able to remove a previously uploaded poster image, reverting the film to a poster-less state.
- **FR-LIB-17:** When no poster image is set, the UI shall display a neutral placeholder.

---

### 5.2 Rating System

#### 5.2.1 Add a Rating

- **FR-RAT-01:** The user shall be able to add a new `RatingEntry` to any film at any time, representing a new watch event.
- **FR-RAT-02:** A `RatingEntry` requires a `value` (0.5–5.0, in increments of 0.5) and a `watch_date`.
- **FR-RAT-03:** The `watch_date` shall not be settable to a future date. The system shall reject future dates with a validation error.
- **FR-RAT-04:** Multiple `RatingEntry` records for the same film on the same `watch_date` are permitted (the user may have genuinely re-rated on the same day).

#### 5.2.2 Rating History

- **FR-RAT-05:** The full `RatingEntry` history of a film shall be viewable, ordered by `watch_date` descending (most recent first).
- **FR-RAT-06:** Each entry in the history view shall display: `value`, `watch_date`, and `created_at`.
- **FR-RAT-07:** The user shall be able to delete a specific `RatingEntry` from the history. Deletion shall require confirmation.
- **FR-RAT-08:** The user shall **not** be able to edit the `value` or `watch_date` of an existing `RatingEntry`. To correct an entry, they must delete it and create a new one.

#### 5.2.3 Average Rating

- **FR-RAT-09:** The system shall compute `average_rating` as the arithmetic mean of all `RatingEntry.value` values for that film, rounded to one decimal place.
- **FR-RAT-10:** The `average_rating` shall be recomputed automatically whenever a `RatingEntry` is added or deleted.
- **FR-RAT-11:** If a film has no `RatingEntry` records, the `average_rating` shall be displayed as "Not yet rated" (or equivalent neutral indicator), never as zero.

---

### 5.3 Tagging

- **FR-TAG-01:** The user shall be able to create new tags by typing a tag name and confirming.
- **FR-TAG-02:** Tag names shall be unique in a case-insensitive manner. The system shall prevent creation of a tag whose name matches an existing tag when compared case-insensitively.
- **FR-TAG-03:** The user shall be able to assign one or more existing tags to a film.
- **FR-TAG-04:** The user shall be able to remove a tag from a film without deleting the tag itself.
- **FR-TAG-05:** The user shall be able to delete a tag globally. Deleting a tag shall remove it from all films it was assigned to. This action shall require confirmation and display the number of films that will be affected.
- **FR-TAG-06:** The tag input on a film shall support autocomplete, suggesting existing tags as the user types.

---

### 5.4 Search & Filter

- **FR-SF-01:** The user shall be able to search films by `title` using a free-text search. The search shall be case-insensitive and match substrings (e.g. searching "god" matches "The Godfather").
- **FR-SF-02:** The user shall be able to filter films by one or more **tags** (AND logic: a film must have all selected tags to appear).
- **FR-SF-03:** The user shall be able to filter films by **genre** (exact match, case-insensitive).
- **FR-SF-04:** The user shall be able to filter films by **release year** using a range (from year / to year).
- **FR-SF-05:** The user shall be able to filter films by **average rating** using a minimum threshold (e.g. "only show films rated 3.5 or above").
- **FR-SF-06:** Filters and search can be combined simultaneously. All active criteria are applied together (AND logic across filter types).
- **FR-SF-07:** The user shall be able to sort the results by: `title` (A–Z, Z–A), `release_year` (asc/desc), `average_rating` (asc/desc), `watch_date` of the most recent RatingEntry (asc/desc).
- **FR-SF-08:** The active filter and sort state shall be reflected in the URL (query parameters) so that the view can be bookmarked and shared.
- **FR-SF-09:** The user shall be able to clear all active filters and search with a single action.
- **FR-SF-10:** The total count of films matching the current filter/search criteria shall always be visible.

---

### 5.5 Rewatch Suggestion Engine

#### 5.5.1 Algorithm Contract

The rewatch suggestion feature is powered by an external algorithm supplied by the user. This section defines the contract that the application must honour when integrating it.

- **FR-RW-01:** The application shall invoke the rewatch algorithm as a **pure function** with a well-defined input payload and consume its output to render the suggestion view. The algorithm's internal logic is outside the scope of this document.
- **FR-RW-02:** The application shall pass the following data to the algorithm for every film in the library:

| Input Field | Source | Description |
|---|---|---|
| `film_id` | Film.id | Unique identifier |
| `title` | Film.title | Film title |
| `average_rating` | Computed | Arithmetic mean of all rating entries |
| `rating_history` | List\<RatingEntry\> | Full list of `{ value, watch_date }` tuples, ordered by `watch_date` ascending |
| `tags` | List\<Tag.name\> | Names of all assigned tags |
| `genre` | Film.genre | Genre string |

- **FR-RW-03:** The algorithm shall return an **ordered list** of objects. Each object in the list must contain at minimum:

| Output Field | Type | Description |
|---|---|---|
| `film_id` | UUID | Identifies which film is being suggested |
| `score` | Decimal | A numeric score used to order suggestions (higher = stronger suggestion). Range and unit are defined by the algorithm. |
| `reason` | String (optional) | A human-readable explanation of why this film is suggested (may be null/absent) |

- **FR-RW-04:** The application shall not modify the order returned by the algorithm. The first item in the returned list is displayed as the top suggestion.
- **FR-RW-05:** The algorithm shall be re-invoked whenever the underlying film data changes (new rating added, film deleted, etc.), so that the suggestion list remains current.
- **FR-RW-06:** If the algorithm returns an empty list (e.g. no films qualify), the view shall display an appropriate empty state message.
- **FR-RW-07:** If the algorithm throws an error or times out, the view shall display a non-blocking error message. The rest of the application shall remain fully functional.

---

### 5.6 Offline & Sync

#### 5.6.1 Offline Availability

- **FR-OFF-01:** All three views (Rewatch Suggestion, Search & Filter, Film Detail) shall be fully usable when the backend is unreachable, using data from the local cache.
- **FR-OFF-02:** The application shall be installable as a **Progressive Web App (PWA)** on mobile devices, enabling home-screen access and offline operation without requiring a native app.
- **FR-OFF-03:** On first load (when online), the application shall cache all film, rating, and tag data locally so that subsequent offline sessions have access to the full library.
- **FR-OFF-04:** The offline experience shall be functionally identical to the online experience for all read operations. There shall be no "offline mode" with reduced functionality for browsing.

#### 5.6.2 Offline Writes & Sync Queue

- **FR-OFF-05:** Any write operation (create film, edit film, delete film, add rating, delete rating, create tag, assign/remove tag) performed while offline shall be committed to the local store immediately and added to a **persistent sync queue**.
- **FR-OFF-06:** The sync queue shall survive app restarts, tab closures, and device reboots. A pending write shall not be lost unless the user explicitly discards it.
- **FR-OFF-07:** When connectivity to the backend is restored, the application shall automatically process the sync queue in the order operations were originally performed (FIFO).
- **FR-OFF-08:** Each sync queue entry shall record: the operation type, the full payload, and the UTC timestamp of the original local write.

#### 5.6.3 Conflict Resolution

- **FR-OFF-09:** Because the application has a single user, true multi-party write conflicts are not expected. The conflict resolution strategy shall be **last-write-wins by `updated_at` timestamp**: the record with the later `updated_at` value is authoritative.
- **FR-OFF-10:** If the backend rejects a queued operation during sync (e.g. the record was deleted on another device before the queue was processed), the application shall surface a clear, non-blocking notification describing which operation failed and why. It shall not silently discard the failure.
- **FR-OFF-11:** After a successful sync, the local cache shall be updated to reflect the authoritative backend state, resolving any divergence.

#### 5.6.4 Connectivity & Sync Status

- **FR-OFF-12:** The UI shall display a persistent, unobtrusive indicator of the current connectivity state: **Online**, **Offline**, or **Syncing**.
- **FR-OFF-13:** When there are pending unsynced operations, the UI shall indicate the number of pending changes (e.g. "3 changes pending sync").
- **FR-OFF-14:** The user shall be able to manually trigger a sync attempt at any time via a visible action (e.g. a "Sync now" button), in addition to the automatic sync on connectivity restoration.

---

## 6. Extensibility Requirements

These requirements ensure the application can accommodate new features, views, and integrations without requiring structural rework of existing components.

### 6.1 New Views

- **FR-EXT-01:** Adding a new view to the application shall not require changes to the data access layer or the business logic layer.
- **FR-EXT-02:** The navigation structure shall be designed so that new entries can be added to it without modifying existing navigation items.
- **FR-EXT-03:** Shared UI components (cards, rating display, tag chips, etc.) shall be implemented as reusable, self-contained components so that new views can compose them without duplication.

### 6.2 New Film Fields

- **FR-EXT-04:** Adding a new optional field to the Film entity shall require changes only in the data model, the API schema, and the relevant UI form. No other layer shall require modification.
- **FR-EXT-05:** The Search & Filter feature shall be designed so that new filterable fields can be added by extending the filter configuration, not by rewriting the filter component.

### 6.3 External API Integration

- **FR-EXT-06:** The application shall be designed so that an external film metadata API (e.g. TMDB) can be integrated as an **optional lookup step** during film creation, without modifying the existing manual entry flow.
- **FR-EXT-07:** The integration point for such an adapter shall be explicitly defined in the film creation flow (e.g. a designated "search external source" action that pre-fills the form). The form submission and persistence logic shall remain unchanged regardless of whether the adapter is active.
- **FR-EXT-08:** It shall be possible to add, remove, or swap an external API adapter purely through configuration and the addition of a new adapter module — without touching core business logic.

### 6.4 Algorithm Extensibility

- **FR-EXT-09:** The rewatch algorithm module shall expose a single, documented function signature. Replacing or updating the algorithm shall require only modifying the contents of that module, with no changes to the calling code.
- **FR-EXT-10:** Additional scoring or suggestion algorithms (e.g. "films similar to ones I rated highly") shall be addable as separate modules following the same contract, selectable via configuration.

### 6.5 API Extensibility

- **FR-EXT-11:** New API endpoints shall follow the established versioned URL structure and the documented request/response conventions, ensuring consistency across the growing API surface.
- **FR-EXT-12:** The API shall be designed so that a future additional client (e.g. a mobile native app, a CLI tool) can consume it without requiring backend changes.

### 6.6 Deployment & Sync Strategy

- **FR-EXT-13:** The deployment topology (local laptop vs. always-on server vs. any future arrangement) shall be switchable purely through configuration. No code change in the frontend or backend shall be required to move between topologies.
- **FR-EXT-14:** The sync module shall be designed so that the underlying sync strategy (e.g. switching from a REST-based sync to a WebSocket-based real-time sync) can be replaced by swapping the sync module implementation, with no changes required in the UI or business logic layers.

---

## 7. UI / UX Requirements

The application consists of exactly **three views**. Navigation between views shall be possible at all times via a persistent navigation element (e.g. top navigation bar or bottom tab bar on mobile).

---

### 7.1 Rewatch Suggestion View

**Purpose:** The primary discovery view — presents algorithmically ranked films the user should consider rewatching.

**Layout:**

- Displayed as a **responsive card grid**.
  - Desktop: 3–4 cards per row.
  - Tablet: 2 cards per row.
  - Mobile: 1 card per row (full-width cards).
- Cards are ordered strictly by the algorithm's output order (highest suggestion score first).

**Film Card — Required Elements:**

| Element | Source | Notes |
|---|---|---|
| Poster image | Film.poster_image | Displays placeholder if no image is set |
| Title | Film.title | Truncated with ellipsis if too long for the card width |
| Release year | Film.release_year | |
| Average rating | Film.average_rating | Displayed as a star or numeric representation |
| Reason | RewatchSuggestion.reason | Displayed only if the algorithm provides a `reason`; hidden otherwise |

**Interactions:**

- Clicking/tapping a card navigates to the **Film Detail View** for that film.
- A visible **refresh** action shall allow the user to manually re-trigger the algorithm.
- The view shall display a loading indicator while the algorithm is computing.
- An **empty state** is shown when no suggestions are returned (FR-RW-06).
- An **error state** is shown if the algorithm fails (FR-RW-07), without hiding the cards from the previous successful run.

---

### 7.2 Search & Filter View

**Purpose:** Allows the user to browse the complete film library and narrow it down through search and filters.

**Layout:**

- A **filter/search panel** at the top or side of the view, containing:
  - Free-text search input (searches `title`).
  - Tag filter (multi-select, autocomplete).
  - Genre filter (dropdown or multi-select).
  - Release year range (two numeric inputs: "from" and "to").
  - Minimum average rating filter (slider or select: 0.5, 1.0, …, 5.0).
  - Sort control (field + direction).
  - "Clear all filters" button.
  - Result count indicator (e.g. "24 films").
- The results area below/beside the filter panel displays matching films as a **list or grid** (user may toggle between views if feasible).

**Film Result Item — Required Elements:**

| Element | Source |
|---|---|
| Poster image (thumbnail) | Film.poster_image |
| Title | Film.title |
| Release year | Film.release_year |
| Director | Film.director |
| Genre | Film.genre |
| Average rating | Film.average_rating |
| Tags | Film.tags |

**Interactions:**

- Clicking/tapping a result item navigates to the **Film Detail View**.
- A clearly visible **"Add Film"** action (e.g. floating button or top-bar button) opens the Add Film form (modal or inline panel).
- Search and filter results update in real-time (or on input debounce) without a full page reload.
- Active filters shall be visually indicated (e.g. highlighted filter chips).

**Add Film Form (modal/panel):**

- Fields: `title` (required), `release_year` (required), `director`, `genre`, `poster_image`, `tags`, and optionally a first `RatingEntry` (`value` + `watch_date`).
- Inline validation feedback before submission.
- Duplicate detection warning (FR-LIB-05) displayed inline before the user can confirm.
- On successful save, the new film appears in the result list and the form closes.

---

### 7.3 Film Detail View

**Purpose:** The full record for a single film — all metadata, the complete rating history, and edit/delete controls.

**Layout — two logical sections:**

#### Section A: Film Metadata

| Element | Notes |
|---|---|
| Poster image (large) | Full-size display; upload/remove controls visible in edit mode |
| Title | Editable inline or via edit form |
| Release year | |
| Director | |
| Genre | |
| Tags | Displayed as chips; add/remove tags directly from this view |
| Average rating | Prominently displayed; visually distinguished (e.g. large star rating component) |
| Created / updated timestamps | Displayed in a subdued style |

- An **Edit** button opens all metadata fields for editing in place or in a modal.
- A **Delete Film** button triggers a confirmation dialog (FR-LIB-11) before deletion. After deletion, the user is navigated back to the Search & Filter View.

#### Section B: Rating History

- Displayed as a **chronological list**, most recent entry first.
- Each entry shows: `value` (as stars or numeric), `watch_date`, `created_at`.
- Each entry has a **Delete** action with confirmation (FR-RAT-07).
- An **"Add Rating"** action (button) opens an inline form or modal with: `value` (star picker, 0.5–5.0 in 0.5 increments) and `watch_date` (date picker, no future dates).
- If the rating history is empty, a clear empty state is shown with a prompt to add the first rating.

---

### 7.4 Responsive Design

- The application shall be fully usable at viewport widths from **320 px** to **2560 px**.
- All interactive elements (buttons, inputs, cards) shall have touch targets of at least **44 × 44 px** on mobile.
- Typography, spacing, and layout shall adapt fluidly between breakpoints. No horizontal scrolling shall occur on any view at any supported viewport width.
- The navigation element shall adapt between a top bar (desktop) and a bottom tab bar or hamburger menu (mobile).
- Images shall be responsive and never cause layout overflow.

---

## 8. Non-Functional Requirements

### 8.1 Performance

- **NFR-PERF-01:** Initial page load (first contentful paint) shall occur within **2 seconds** on a standard broadband connection (≥ 10 Mbps).
- **NFR-PERF-02:** Navigation between views shall feel instantaneous (< 200 ms perceived transition time) once the application is loaded.
- **NFR-PERF-03:** Search and filter results shall update within **300 ms** of the user finishing input (after debounce).
- **NFR-PERF-04:** The application shall remain performant with a library of up to **10,000 film records**.

### 8.2 Data Persistence

- **NFR-DATA-01:** All film, rating, and tag data shall be persisted in a server-side data store as the authoritative record. Data must survive browser refreshes, tab closures, and device changes once synced.
- **NFR-DATA-02:** The frontend shall maintain a **local persistent cache** (e.g. IndexedDB) that mirrors the server-side data store and additionally holds any unsynced pending writes. This local cache is the primary read source for all views.
- **NFR-DATA-03:** Write operations shall be committed to the local cache immediately and confirmed to the user at that point. The background sync to the backend is a separate, asynchronous step. The user shall be clearly informed of the distinction between "saved locally" and "synced to server" states where relevant (see FR-OFF-12, FR-OFF-13).

### 8.3 Data Integrity

- **NFR-INT-01:** `average_rating` shall always reflect the current state of `rating_history`. There shall be no scenario in which a stale average is displayed.
- **NFR-INT-02:** Deleting a film shall atomically delete all its associated `RatingEntry` records. Partial deletions are not acceptable.
- **NFR-INT-03:** All user inputs shall be validated on both the client side (immediate feedback) and the server side (authoritative enforcement).

### 8.4 Browser Support

- **NFR-BROWSER-01:** The application shall be fully functional in the **two most recent stable releases** of the following browsers: Google Chrome, Mozilla Firefox, Apple Safari, Microsoft Edge.
- **NFR-BROWSER-02:** The application shall not rely on any browser-specific APIs that are not available across all four target browsers.

### 8.5 Accessibility

- **NFR-A11Y-01:** The application shall meet **WCAG 2.1 Level AA** compliance.
- **NFR-A11Y-02:** All interactive elements shall be keyboard-navigable.
- **NFR-A11Y-03:** All images shall have descriptive `alt` text; poster images shall use the film title as alt text.
- **NFR-A11Y-04:** Colour shall not be the sole means of conveying information (e.g. rating values must also be conveyed numerically or via accessible labels).

### 8.6 Reliability

- **NFR-REL-01:** Failed write operations (network errors, server errors) shall surface a clear, human-readable error message. The application shall not silently discard user input.
- **NFR-REL-02:** The application shall handle the rewatch algorithm failing gracefully without crashing or blocking other functionality (FR-RW-07).

### 8.7 Maintainability

- **NFR-MAINT-01:** All API endpoints shall be documented in an OpenAPI / Swagger specification, kept up to date as endpoints are added or changed.
- **NFR-MAINT-02:** Business logic shall not reside in UI components, API route handlers, or database queries. It shall live exclusively in the business logic layer (see Section 3.1).
- **NFR-MAINT-03:** All error responses from the API shall follow a single, consistent error schema (e.g. `{ "error": { "code": "...", "message": "..." } }`). No endpoint shall invent its own error format.
- **NFR-MAINT-04:** Environment-specific configuration (database URLs, external API keys, ports) shall never be hardcoded. All such values shall be read from environment variables or a configuration file that is excluded from version control.
- **NFR-MAINT-05:** The codebase shall include a top-level README that documents how to run the application locally, how to run tests, and where to find the API documentation.

### 8.8 Offline & Sync

- **NFR-OFF-01:** The application shall achieve a **Lighthouse PWA score of 90 or above**, confirming installability, service worker registration, and offline capability.
- **NFR-OFF-02:** The service worker shall cache all static application assets (HTML, CSS, JS, fonts, icons) on first install, so the application shell loads instantly without a network request on subsequent visits.
- **NFR-OFF-03:** The local data cache shall be able to hold the full film library (up to 10,000 records as per NFR-PERF-04) without degrading read performance below the thresholds in Section 8.1.
- **NFR-OFF-04:** The sync queue shall be persisted in a durable local store (e.g. IndexedDB). It shall not be held in memory alone; entries must survive a full browser or device restart.
- **NFR-OFF-05:** Sync processing shall be **idempotent**: if the same queued operation is submitted to the backend more than once (e.g. due to a network timeout where the first attempt actually succeeded), the backend shall produce the same result without creating duplicate records or returning an unrecoverable error.
- **NFR-OFF-06:** The time from backend connectivity being restored to the sync queue being fully processed shall not exceed **10 seconds** for a queue of up to 50 pending operations under normal network conditions.
- **NFR-OFF-07:** The backend's base URL shall be the **single configuration value** required to point the frontend at a different backend host. No other code or configuration change shall be needed to switch deployment topology.

---
