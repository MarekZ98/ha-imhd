import { defineConfig } from 'vitest/config';

// Library build: one minified ES module, written next to the integration (served by Home Assistant).
export default defineConfig({
  build: {
    lib: {
      entry: 'src/imhd-departures-card.ts',
      formats: ['es'],
      fileName: () => 'imhd-departures-card.js',
    },
    outDir: '../custom_components/imhd/frontend',
    emptyOutDir: false,
    minify: true,
    sourcemap: false,
  },
  test: {
    include: ['test/**/*.test.ts'],
  },
});
