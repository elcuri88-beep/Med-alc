/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

declare const process: { env: Record<string, string | undefined> };
const artifact = !!process.env.VITE_ARTIFACT; // versión de un solo archivo para el visor de artefactos (sin service worker)

export default defineConfig({
  resolve: artifact ? { alias: { 'virtual:pwa-register': new URL('./src/pwa-stub.ts', import.meta.url).pathname } } : {},
  build: artifact ? { cssCodeSplit: false, assetsInlineLimit: 100000000 } : {},
  plugins: [
    react(),
    ...(artifact ? [] : [VitePWA({
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
    })]),
  ],
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
