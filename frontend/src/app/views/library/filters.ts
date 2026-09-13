/**
 * The Library's filter criteria (REQ §7.2) — the extensibility seam FR-EXT-05
 * exists for. Adding a search dimension (director FR-SF-02, tags/genre/year/
 * min-rating FR-SF-06..09) means one field on `LibraryCriteria` plus one
 * entry in `PREDICATES`; the view stays untouched.
 */
import type { Film } from '../../domain/film/model';

export interface LibraryCriteria {
  /** Free text matched against every title of a film (FR-SF-01). */
  readonly title: string;
}

export const NO_CRITERIA: LibraryCriteria = { title: '' };

/**
 * One entry per criterion, each returning the predicate to apply — or `null`
 * when the criterion holds no value and therefore narrows nothing.
 */
const PREDICATES: readonly ((criteria: LibraryCriteria) => ((film: Film) => boolean) | null)[] = [
  ({ title }) => {
    const query = words(title);
    if (query.length === 0) return null;
    return (film) => titleScore(query, film) > 0;
  },
];

/** Lowercased, accent-free, punctuation-free words — "L'Été à Paris" → ['l', 'ete', 'a', 'paris']. */
function words(text: string): readonly string[] {
  return text
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((word) => word !== '');
}

/** The best score any of a film's titles reaches — FR-SF-01 searches all of them, not just the primary one. */
function titleScore(query: readonly string[], film: Film): number {
  return Math.max(0, ...film.titles.map((title) => scoreTitle(query, words(title.value))));
}

/**
 * A title's total match quality: every query word has to appear somewhere in it,
 * in any order ("in love" finds "In the Mood for Love"), and each contributes its
 * own quality. One missing word scores the title out entirely.
 *
 * ponytail: a typo inside a *partial* word misses ("intrestel" does not reach
 * "interstellar") — the distance compares whole words, and the length gap alone
 * blows the budget. Upgrade path is scoring prefixes separately, or Fuse.js.
 */
function scoreTitle(query: readonly string[], title: readonly string[]): number {
  let total = 0;
  for (const word of query) {
    const best = Math.max(0, ...title.map((candidate) => wordScore(candidate, word)));
    if (best === 0) return 0;
    total += best;
  }
  return total;
}

/**
 * How well one title word answers one query word: 3 the same word, 2 contains it,
 * 1 within the typo budget, 0 unrelated. The ladder is what sorts a title of real
 * hits above one that needed a typo — "in love" puts "In the Mood for Love" (3+3)
 * over "How to Lose a Guy in 10 Days" (3+1, `love` reaching only `lose`).
 */
function wordScore(candidate: string, word: string): number {
  if (candidate === word) return 3;
  if (candidate.includes(word)) return 2;
  return isWithinTypoBudget(candidate, word, typoBudget(word)) ? 1 : 0;
}

/**
 * Edits tolerated in a word: none below four letters, where a single edit turns
 * one real word into another ("in" into "it"), then one per further four —
 * capped at two, past which the matches stop feeling like the same word.
 */
function typoBudget(word: string): number {
  return Math.min(2, Math.floor(word.length / 4));
}

/** Levenshtein distance, abandoned as soon as every path has overrun `budget`. */
function isWithinTypoBudget(a: string, b: string, budget: number): boolean {
  if (Math.abs(a.length - b.length) > budget) return false;
  let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i++) {
    const current = [i];
    for (let j = 1; j <= b.length; j++) {
      current[j] = Math.min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    if (Math.min(...current) > budget) return false;
    previous = current;
  }
  return previous[b.length] <= budget;
}

/**
 * The films matching every active criterion (AND logic, FR-SF-03), best title
 * match first. Only the title has a notion of quality — the other criteria are
 * yes/no — so an unsearched library keeps the order it arrived in, which leaves
 * the eventual sort control (FR-SF-10) owning that order alone.
 */
export function filterFilms(films: readonly Film[], criteria: LibraryCriteria): readonly Film[] {
  const active = PREDICATES.map((predicate) => predicate(criteria)).filter((predicate) => predicate !== null);
  const matches = films.filter((film) => active.every((predicate) => predicate(film)));
  const query = words(criteria.title);
  if (query.length === 0) return matches;
  return matches
    .map((film) => ({ film, score: titleScore(query, film) }))
    .sort((a, b) => b.score - a.score)
    .map(({ film }) => film);
}

/** Whether anything currently narrows the library — drives the clear action (FR-SF-04). */
export function hasActiveCriteria(criteria: LibraryCriteria): boolean {
  return PREDICATES.some((predicate) => predicate(criteria) !== null);
}
