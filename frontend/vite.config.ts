// (c) 2026 Tanishk Kamra | All rights reserved | github.com/TanishkKamra/hceson | tkp-2603f7a67b-072ff1󠁻󠁴󠁫󠁰󠀭󠀲󠀶󠀰󠀳󠁦󠀷󠁡󠀶󠀷󠁢󠀭󠀰󠀷󠀲󠁦󠁦󠀱󠁽
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
