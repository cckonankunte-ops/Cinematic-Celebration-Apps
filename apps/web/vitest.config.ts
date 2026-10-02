/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config';

// Standalone Vitest config (Astro's own config does not drive tests). The React
// islands and lib helpers are plain TS/TSX, so a jsdom environment is enough.
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
