/**
 * Re-themes the film detail view from the poster's seed palette (REQ §7.3
 * `poster_palette`, DESIGN §6.5 shared/).
 *
 * The backend ranks up to 4 swatches by dominance (FR-LIB-13/14); this maps
 * them to Material 3 roles by position: the first (the poster's true
 * majority colour, background/neutral included) drives the surfaces, the
 * rest drive primary/secondary/tertiary. Builds a light and a dark
 * `DynamicScheme` from that mapping — the "Content" variant keeps hue/chroma
 * closer to the source than TonalSpot, which the app's global theme already
 * uses — and pairs each role's two tones into one `light-dark()` value per
 * `--mat-sys-*` custom property. `styles.scss` sets `color-scheme` from
 * `ThemeService`'s Light/Dark/Auto choice, so `light-dark()` picks the right
 * side of the pair with zero extra JS: the poster theme keeps following the
 * user's theme switch for free.
 *
 * Only hue/chroma come from the poster — tone (lightness) still comes from
 * the light/dark scheme itself, so e.g. a black-dominant poster gives
 * dark-gray surfaces in dark mode and light-gray ones in light mode, never a
 * literally black or white app background.
 */
import {
  DynamicScheme,
  Hct,
  SchemeContent,
  TonalPalette,
  Variant,
  argbFromHex,
  hexFromArgb,
} from '@material/material-color-utilities';

/**
 * The `--mat-sys-*` colour roles this view overrides, each paired with the
 * `DynamicScheme` getter that produces it. Kept in the same order Angular
 * Material documents them; verified against
 * `@angular/material/core/tokens/m3/_md-sys-color.scss`.
 */
const ROLES: readonly (readonly [role: string, pick: (scheme: DynamicScheme) => number])[] = [
  ['primary', (s) => s.primary],
  ['on-primary', (s) => s.onPrimary],
  ['primary-container', (s) => s.primaryContainer],
  ['on-primary-container', (s) => s.onPrimaryContainer],
  ['secondary', (s) => s.secondary],
  ['on-secondary', (s) => s.onSecondary],
  ['secondary-container', (s) => s.secondaryContainer],
  ['on-secondary-container', (s) => s.onSecondaryContainer],
  ['tertiary', (s) => s.tertiary],
  ['on-tertiary', (s) => s.onTertiary],
  ['tertiary-container', (s) => s.tertiaryContainer],
  ['on-tertiary-container', (s) => s.onTertiaryContainer],
  // The favourite heart reads --favorite-color, which aliases --mat-sys-error
  // (styles.scss) — the Content scheme's error role stays red regardless of
  // the seed, same M3 convention the app's default theme already relies on.
  ['error', (s) => s.error],
  ['on-error', (s) => s.onError],
  ['error-container', (s) => s.errorContainer],
  ['on-error-container', (s) => s.onErrorContainer],
  ['surface', (s) => s.surface],
  ['on-surface', (s) => s.onSurface],
  ['surface-variant', (s) => s.surfaceVariant],
  ['on-surface-variant', (s) => s.onSurfaceVariant],
  ['surface-container-lowest', (s) => s.surfaceContainerLowest],
  ['surface-container-low', (s) => s.surfaceContainerLow],
  ['surface-container', (s) => s.surfaceContainer],
  ['surface-container-high', (s) => s.surfaceContainerHigh],
  ['surface-container-highest', (s) => s.surfaceContainerHighest],
  ['surface-bright', (s) => s.surfaceBright],
  ['surface-dim', (s) => s.surfaceDim],
  ['inverse-surface', (s) => s.inverseSurface],
  ['inverse-on-surface', (s) => s.inverseOnSurface],
  ['inverse-primary', (s) => s.inversePrimary],
  ['outline', (s) => s.outline],
  ['outline-variant', (s) => s.outlineVariant],
  ['shadow', (s) => s.shadow],
  ['scrim', (s) => s.scrim],
  ['surface-tint', (s) => s.surfaceTint],
];

// ponytail: caps on the neutral/neutral-variant chroma pulled from the
// dominant swatch — a saturated poster background would otherwise tint
// surfaces (cards, the app bar) as hard as the accents, which reads as
// garish rather than themed. Raise these if surfaces should track the
// poster more aggressively.
const _NEUTRAL_CHROMA_CAP = 12;
const _NEUTRAL_VARIANT_CHROMA_CAP = 16;

function hctOf(hex: string): Hct {
  return Hct.fromInt(argbFromHex(hex));
}

/**
 * One light or dark `DynamicScheme` for `palette`. A single-entry palette is
 * today's behaviour verbatim — a plain Content scheme seeded from that one
 * colour. A longer palette maps positionally: `palette[0]` (the true
 * dominant colour) seeds the neutral/neutral-variant palettes that drive
 * surfaces, `palette[1]` (or `palette[0]` again, with fewer than 2 entries)
 * seeds the scheme itself and `primary`, and `palette[2]`/`palette[3]`, when
 * present, seed `secondary`/`tertiary` — otherwise those fall back to the
 * Content spec's own derivation from the primary seed, same as a plain
 * `SchemeContent`.
 */
function schemeFor(palette: readonly string[], isDark: boolean): DynamicScheme {
  const primaryHex = palette[1] ?? palette[0];
  if (palette.length === 1) {
    return new SchemeContent(hctOf(primaryHex), isDark, 0);
  }

  const neutralSeed = hctOf(palette[0]);
  return new DynamicScheme({
    sourceColorHct: hctOf(primaryHex),
    variant: Variant.CONTENT,
    contrastLevel: 0,
    isDark,
    primaryPalette: TonalPalette.fromInt(argbFromHex(primaryHex)),
    ...(palette[2] ? { secondaryPalette: TonalPalette.fromInt(argbFromHex(palette[2])) } : {}),
    ...(palette[3] ? { tertiaryPalette: TonalPalette.fromInt(argbFromHex(palette[3])) } : {}),
    neutralPalette: TonalPalette.fromHueAndChroma(neutralSeed.hue, Math.min(neutralSeed.chroma, _NEUTRAL_CHROMA_CAP)),
    neutralVariantPalette: TonalPalette.fromHueAndChroma(
      neutralSeed.hue,
      Math.min(neutralSeed.chroma, _NEUTRAL_VARIANT_CHROMA_CAP),
    ),
  });
}

/**
 * `light-dark(<light>, <dark>)` for every role above, keyed by
 * `--mat-sys-<role>` — apply directly as inline host styles. Contrast level
 * 0 (standard, not the -1..1 accessibility dial) for both schemes.
 */
export function posterThemeStyles(palette: readonly string[]): Record<string, string> {
  const lightScheme = schemeFor(palette, false);
  const darkScheme = schemeFor(palette, true);
  const styles: Record<string, string> = {};
  for (const [role, pick] of ROLES) {
    styles[`--mat-sys-${role}`] = `light-dark(${hexFromArgb(pick(lightScheme))}, ${hexFromArgb(pick(darkScheme))})`;
  }
  return styles;
}
