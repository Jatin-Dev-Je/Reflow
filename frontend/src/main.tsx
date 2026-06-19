/**
 * Vite entrypoint — mounts <App /> on #root.
 *
 * Side-effect imports at the top: global stylesheet + Vellum tokens.
 */

import { createRoot } from "react-dom/client";

import { App } from "@/app/boot";
import "@/styles/globals.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("#root element not found in index.html");
}

createRoot(container).render(<App />);
