/** DTO → domain mapping and the §7.1 "Rewatch status" wording. */
import type { Film } from '../film/model';
import { dueLabelFor, toRewatchCardVm, toRewatchSuggestion } from './mapper';

const HEAT: Film = {
  id: 'f1',
  primaryTitle: 'Heat',
  releaseYear: 1995,
  director: 'Michael Mann',
  runtimeMinutes: 170,
  genres: ['Crime'],
  tags: ['heist'],
  posterImage: null,
  averageRating: 4,
  isFavorite: true,
  titles: [{ value: 'Heat', isPrimary: true, isOriginal: true }],
};

describe('toRewatchSuggestion', () => {
  it('maps the snake_case wire shape to the domain model', () => {
    expect(toRewatchSuggestion({ film_id: 'f1', days_until_next_rewatch: -3 })).toEqual({
      filmId: 'f1',
      daysUntilNextRewatch: -3,
    });
  });
});

describe('dueLabelFor', () => {
  it('reads "Due now" at zero', () => {
    expect(dueLabelFor(0)).toBe('Due now');
  });

  it('counts the days a film is overdue', () => {
    expect(dueLabelFor(-12)).toBe('Overdue by 12 days');
  });

  it('says "day" for exactly one', () => {
    expect(dueLabelFor(-1)).toBe('Overdue by 1 day');
  });
});

describe('toRewatchCardVm', () => {
  it('shapes the §7.1 card from the film and its suggestion', () => {
    const card = toRewatchCardVm(HEAT, { filmId: 'f1', daysUntilNextRewatch: -5 });

    expect(card).toEqual({
      id: 'f1',
      title: 'Heat',
      year: 1995,
      posterImage: null,
      ratingStars: ['star', 'star', 'star', 'star', 'star_border'],
      ratingLabel: 'Average rating: 4.0 out of 5',
      isFavorite: true,
      dueLabel: 'Overdue by 5 days',
    });
  });

  it('carries the unrated placeholder through', () => {
    const card = toRewatchCardVm({ ...HEAT, averageRating: null }, { filmId: 'f1', daysUntilNextRewatch: 0 });

    expect(card.ratingStars).toBeNull();
    expect(card.ratingLabel).toBe('Not rated');
  });
});
