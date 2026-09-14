/**
 * The app's one star-rendering rule (FR-RAT-09/11/13, DESIGN §6.5 shared/).
 *
 * Extracted from the library view when the rewatch grid needed the same five
 * icons: two views rounding half-stars independently would eventually disagree.
 * These are functions, not a component — the markup they feed is a five-item
 * `@for`, which is not yet worth a component of its own.
 */

/** Material icon names for the five positions, rounded to the nearest half star; `null` for an unrated film. */
export function ratingStarsFor(rating: number | null): readonly string[] | null {
  if (rating === null) return null;
  const rounded = Math.round(rating * 2) / 2;
  return Array.from({ length: 5 }, (_, index) => {
    const position = index + 1;
    if (rounded >= position) return 'star';
    if (position - rounded === 0.5) return 'star_half';
    return 'star_border';
  });
}

/** The accessible label for the star row — the icons themselves are `aria-hidden`. */
export function ratingLabelFor(rating: number | null): string {
  return rating === null ? 'Not rated' : `Average rating: ${rating.toFixed(1)} out of 5`;
}
