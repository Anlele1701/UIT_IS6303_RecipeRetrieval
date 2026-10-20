import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// `npm run dev` forwards API calls to uvicorn; set API_URL if it is not on port 8000.
const api = process.env.API_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // POST /chat is the API; GET /chat is this app's page, served by Vite itself in dev
    proxy: {
      '/chat': { target: api, bypass: req => (req.method === 'GET' ? req.url : undefined) },
      ...Object.fromEntries(['/search', '/strategies', '/categories', '/health', '/docs', '/openapi.json', '/sessions', '/recipes',
      '/feedback', '/patients'].map(p => [p, api])),
    },
  },
  // `npm run build` writes the app where FastAPI serves it (api/main.py).
  build: { outDir: '../api/static', emptyOutDir: true },
})
