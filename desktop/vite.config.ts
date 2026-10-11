import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath, URL } from 'node:url';
export default defineConfig({
  base: './', plugins: [tailwindcss(), svelte()],
  resolve: { alias: { '$lib/components/ui': fileURLToPath(new URL('./src/lib/ui', import.meta.url)), '$lib': fileURLToPath(new URL('./src/lib', import.meta.url)) } },
  server: { proxy: { '/api': 'http://127.0.0.1:8787' } }
});
