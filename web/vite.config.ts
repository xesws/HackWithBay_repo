import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GraphJudge SPA (Track C). Static build → dist/ → Butterbase frontend deploy.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  // bind all interfaces (IPv4 + IPv6) so RunPod / VS Code port-forwarders that
  // dial 127.0.0.1 aren't refused by a localhost-only (::1) bind.
  server: { host: true },
});
