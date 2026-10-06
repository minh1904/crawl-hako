import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Build ra thẳng package Python để `lnget ui` phục vụ, người dùng không cần Node.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  build: { outDir: "../lnget/web/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
})
