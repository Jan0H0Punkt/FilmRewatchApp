import { Pipe, PipeTransform } from '@angular/core';

type Star = 'full' | 'half' | 'empty';

@Pipe({ name: 'ratingStars', pure: true })
export class RatingStarsPipe implements PipeTransform {
  transform(count: number, max = 5): Star[] {
    const c = Math.max(0, Number(count) || 0);
    const rounded = Math.round(c * 2) / 2; // nearest 0.5

    const full = Math.floor(rounded);
    const half = rounded - full === 0.5 ? 1 : 0;
    const empty = Math.max(0, max - full - half);

    return [
      ...Array.from({ length: full }).map(() => 'full' as const),
      ...(half ? (['half'] as const) : []),
      ...Array.from({ length: empty }).map(() => 'empty' as const),
    ];
  }
}
