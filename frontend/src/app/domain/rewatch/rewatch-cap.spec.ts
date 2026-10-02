/** Every row of the design's §Cap table, plus the floating-point pitfall it calls out by name. */
import { rewatchCap } from './cap';

describe('rewatchCap', () => {
  it('applies no cap when the share is Off', () => {
    expect(rewatchCap(null, 10, 3)).toBeNull();
  });

  it('applies no cap at a 100% target — the formula would divide by zero', () => {
    expect(rewatchCap(100, 10, 3)).toBeNull();
  });

  it('caps at zero for a 0% target, regardless of watches so far', () => {
    expect(rewatchCap(0, 10, 3)).toBe(0);
  });

  it('caps at zero with no watches yet this year (e.g. 1 January)', () => {
    expect(rewatchCap(50, 0, 0)).toBe(0);
  });

  it('never returns a negative cap when the target is already exceeded', () => {
    expect(rewatchCap(10, 5, 5)).toBe(0);
  });

  it('does not let floating-point error round 0 up to 1 (30%, 10 watches, 3 rewatches)', () => {
    expect(rewatchCap(30, 10, 3)).toBe(0);
  });

  it('rounds up to the smallest k that clears the target', () => {
    // t=0.5: after k more rewatches, (2+k)/(10+k) >= 0.5 first holds at k=6
    // (8/16 = 0.5 exactly) — adding a rewatch also grows the denominator.
    expect(rewatchCap(50, 10, 2)).toBe(6);
  });

  describe('with a watch pace (FR-RW-09)', () => {
    const day10 = new Date(2026, 0, 10); // 1 film every 2 days -> E = 5

    it('measures the share against the expected watches, not the logged ones', () => {
      // E=5, 50 % -> 2.5 rewatches wanted, 1 banked -> ceil(1.5) = 2 (watches=99 is ignored)
      expect(rewatchCap(50, 99, 1, 2, day10)).toBe(2);
    });

    it('never goes negative', () => {
      expect(rewatchCap(20, 0, 3, 2, day10)).toBe(0);
    });

    it('applies no cap when the share is Off or 100', () => {
      expect(rewatchCap(null, 0, 0, 2, day10)).toBeNull();
      expect(rewatchCap(100, 0, 0, 2, day10)).toBeNull();
    });

    it('stays exact in integers (E=10, 30 %, 3 rewatches banked -> 0, not 1)', () => {
      expect(rewatchCap(30, 0, 3, 1, new Date(2026, 0, 10))).toBe(0);
    });
  });
});
