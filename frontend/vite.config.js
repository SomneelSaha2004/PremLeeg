import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Proxy /api to the FastAPI backend during development.
// You can override with: VITE_BACKEND_URL=http://localhost:8000
const backendUrl = process.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
});
