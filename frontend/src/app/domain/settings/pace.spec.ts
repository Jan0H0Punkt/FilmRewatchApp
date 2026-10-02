/** FR-RW-09: the expected-watches count and the snackbar wording. */
import { expectedWatches, paceMessage } from './pace';

describe('expectedWatches', () => {
  it('counts 1 January as day 1', () => {
    expect(expectedWatches(1, new Date(2026, 0, 1))).toBe(1);
    expect(expectedWatches(7, new Date(2026, 0, 1))).toBe(0);
  });

  it('counts 31 December of a leap year as day 366', () => {
    expect(expectedWatches(1, new Date(2024, 11, 31))).toBe(366);
    expect(expectedWatches(7, new Date(2024, 11, 31))).toBe(52);
  });

  it('is not shifted by the time of day', () => {
    expect(expectedWatches(1, new Date(2026, 5, 1, 23, 59))).toBe(expectedWatches(1, new Date(2026, 5, 1, 0, 0)));
  });
});

describe('paceMessage', () => {
  const today = new Date(2026, 0, 10); // day 10 -> expected 5 at one film per 2 days

  it('reports being on pace', () => {
    expect(paceMessage(2, 5, today)).toBe('On pace · 5 films this year');
  });

  it('singularises a single film on pace', () => {
    expect(paceMessage(10, 1, today)).toBe('On pace · 1 film this year');
  });

  it('reports being behind', () => {
    expect(paceMessage(2, 4, today)).toBe('1 film behind pace (4 of 5)');
    expect(paceMessage(2, 2, today)).toBe('3 films behind pace (2 of 5)');
  });

  it('reports being ahead', () => {
    expect(paceMessage(2, 6, today)).toBe('1 film ahead of pace (6 of 5)');
    expect(paceMessage(2, 8, today)).toBe('3 films ahead of pace (8 of 5)');
  });
});
