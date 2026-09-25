import { defineConfig } from 'vitest/config';

// `@material/material-color-utilities` v0.4.0 ships one internal relative
// import without its `.js` extension (dynamiccolor/color_spec_2025.js →
// './dynamic_color'), which Node's own ESM loader rejects — Vitest's default
// pool externalizes node_modules packages to that loader. `server.deps.inline`
// routes this package through Vite's own resolver instead, which tolerates
// the missing extension the same way `ng build`'s esbuild pipeline already
// does. Read via `angular.json`'s test target (`runnerConfig: true`).
export default defineConfig({
  test: {
    server: {
      deps: {
        inline: ['@material/material-color-utilities'],
      },
    },
  },
});
