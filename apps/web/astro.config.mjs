// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwind from '@astrojs/tailwind';

// Static output: no Node server in production (served from Cloudflare Pages).
// Catalog/price/availability data is fetched at RUNTIME by the React islands,
// so a static shell is correct — see README "Static vs dynamic routing".
export default defineConfig({
  site: 'https://cinematiccelebration.in',
  output: 'static',
  integrations: [react(), tailwind()],
});
