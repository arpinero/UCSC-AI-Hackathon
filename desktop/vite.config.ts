import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath, URL } from 'node:url';
export default defineConfig({
  base: './', plugins: [svelte()],
  resolve: { alias: { '$lib/components/ui': fileURLToPath(new URL('./src/lib/ui', import.meta.url)) } },
  server: { proxy: { '/api': 'http://127.0.0.1:8787' } }
});
