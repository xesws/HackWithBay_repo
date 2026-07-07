import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GraphJudge SPA (Track C). Static build → dist/ → Butterbase frontend deploy.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
});
