/** The one star-rendering rule both the library list and the rewatch grid use (FR-RAT-13). */
import { ratingLabelFor, ratingStarsFor } from './rating-stars';

describe('ratingStarsFor', () => {
  it('fills whole stars up to the rating', () => {
    expect(ratingStarsFor(3)).toEqual(['star', 'star', 'star', 'star_border', 'star_border']);
  });

  it('renders a half star for a half-point rating', () => {
    expect(ratingStarsFor(3.5)).toEqual(['star', 'star', 'star', 'star_half', 'star_border']);
  });

  it('rounds to the nearest half star', () => {
    expect(ratingStarsFor(3.7)).toEqual(['star', 'star', 'star', 'star_half', 'star_border']);
  });

  it('returns null for an unrated film', () => {
    // Five empty stars would read as "rated zero", the opposite of "not rated" (FR-RAT-11/13).
    expect(ratingStarsFor(null)).toBeNull();
  });
});

describe('ratingLabelFor', () => {
  it('states the average out of five', () => {
    expect(ratingLabelFor(4.25)).toBe('Average rating: 4.3 out of 5');
  });

  it('says so when nothing was rated', () => {
    expect(ratingLabelFor(null)).toBe('Not rated');
  });
});
