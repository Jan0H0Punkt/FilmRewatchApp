import { posterThemeStyles } from './poster-theme';

function lightHex(styles: Record<string, string>, role: string): string {
  const [, hex] = /^light-dark\((#[0-9a-f]{6}), /.exec(styles[role] ?? '') ?? [];
  expect(hex).toBeDefined();
  return hex!;
}

function rgb(hex: string): [number, number, number] {
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
}

describe('posterThemeStyles', () => {
  it('emits a light-dark() pair for --mat-sys-primary', () => {
    const styles = posterThemeStyles(['#8a2be2']);
    expect(styles['--mat-sys-primary']).toMatch(/^light-dark\(#[0-9a-f]{6}, #[0-9a-f]{6}\)$/);
  });

  it('is deterministic for a fixed palette', () => {
    expect(posterThemeStyles(['#8a2be2'])).toEqual(posterThemeStyles(['#8a2be2']));
  });

  it('derives a reddish primary from a single red seed', () => {
    const styles = posterThemeStyles(['#cc0000']);
    const [r, g, b] = rgb(lightHex(styles, '--mat-sys-primary'));
    expect(r).toBeGreaterThan(g);
    expect(r).toBeGreaterThan(b);
  });

  it('maps a beige-first, brown-second palette to beige-ish surfaces and a brownish primary', () => {
    // Same shape as the Sicario regression (backend/tests/test_poster_palette.py):
    // palette[0] (the true dominant colour) drives surfaces, palette[1] drives primary.
    const styles = posterThemeStyles(['#dbceb5', '#93745a']);

    const [sr, sg, sb] = rgb(lightHex(styles, '--mat-sys-surface'));
    expect(sr).toBeGreaterThanOrEqual(sg);
    expect(sg).toBeGreaterThanOrEqual(sb);

    const [pr, pg, pb] = rgb(lightHex(styles, '--mat-sys-primary'));
    expect(pr).toBeGreaterThan(pg);
    expect(pg).toBeGreaterThan(pb);
  });

  it('is deterministic for a fixed multi-entry palette', () => {
    const palette = ['#dbceb5', '#93745a', '#2f4f4f'];
    expect(posterThemeStyles(palette)).toEqual(posterThemeStyles(palette));
  });
});
