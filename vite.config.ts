/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      workbox: { globPatterns: ['**/*.{js,css,html,svg,json,png}'] },
      manifest: {
        name: 'V60 Academy',
        short_name: 'V60 Academy',
        description: 'Aprendizaje de VMNI con el Philips Respironics BiPAP V60 (uso educativo).',
        lang: 'es-ES',
        display: 'standalone',
        orientation: 'portrait',
        theme_color: '#0f4c81',
        background_color: '#ffffff',
        icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }],
      },
    }),
  ],
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
