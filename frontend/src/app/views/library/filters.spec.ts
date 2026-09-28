/** The Library's title search (FR-SF-01): word order, partial words, and typos. */
import type { Film } from '../../domain/film/model';
import { filterFilms, hasActiveCriteria } from './filters';

function film(id: string, ...titles: readonly string[]): Film {
  return {
    id,
    primaryTitle: titles[0],
    releaseYear: 2000,
    director: 'Someone',
    runtimeMinutes: 100,
    genres: [],
    tags: [],
    posterImage: null,
    letterboxdUrl: null,
    averageRating: null,
    isFavorite: false,
    owned: false,
    titles: titles.map((value, index) => ({ value, isPrimary: index === 0, isOriginal: index === 0 })),
    updatedAt: '2024-01-01T00:00:00Z',
  };
}

const MOOD = film('f1', 'In the Mood for Love');
const INTERSTELLAR = film('f2', 'Interstellar');
const AMELIE = film('f3', 'Amélie', 'Le Fabuleux Destin d’Amélie Poulain');
/** Reaches "love" only through the typo budget (`lose`) — the weak match ranking has to demote. */
const LOSE = film('f4', 'How to Lose a Guy in 10 Days');
/** Deliberately not the order any result is expected in: ranking has to do the reordering. */
const LIBRARY = [LOSE, MOOD, INTERSTELLAR, AMELIE];

function search(title: string): readonly Film[] {
  return filterFilms(LIBRARY, { title });
}

describe('title search', () => {
  it('matches words in any order, with gaps between them', () => {
    expect(search('love mood')).toEqual([MOOD]);
  });

  it('ranks real word hits above typo hits', () => {
    expect(search('in love')).toEqual([MOOD, LOSE]);
  });

  it('puts the most recently edited film first when nothing is searched', () => {
    const recent = { ...MOOD, updatedAt: '2024-03-01T00:00:00Z' };
    const newest = { ...AMELIE, updatedAt: '2024-03-01T00:00:00.5Z' };
    expect(filterFilms([recent, INTERSTELLAR, newest], { title: '' })).toEqual([newest, recent, INTERSTELLAR]);
  });

  it('matches partial words', () => {
    expect(search('inter')).toEqual([INTERSTELLAR]);
  });

  it('tolerates a typo once the word is long enough', () => {
    expect(search('intersteller')).toEqual([INTERSTELLAR]);
    expect(search('mod')).toEqual([]);
  });

  it('ignores accents and punctuation, on both sides', () => {
    expect(search('amelie')).toEqual([AMELIE]);
    expect(search('d’amelie poulain')).toEqual([AMELIE]);
  });

  it('narrows nothing on a query without words', () => {
    expect(hasActiveCriteria({ title: '  ' })).toBe(false);
    expect(search('  ')).toEqual(LIBRARY);
  });
});
