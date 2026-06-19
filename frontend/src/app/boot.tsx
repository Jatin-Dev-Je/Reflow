import { StrictMode } from "react";
import { RouterProvider } from "react-router-dom";

import { Providers } from "@/app/providers";
import { router } from "@/app/router";

/**
 * Root <App />. Mounts the declarative router inside the global providers.
 *
 * Everything visible flows through the router → feature page components.
 * The Vellum BootScreen is gone — it served its "design system loaded"
 * purpose; real screens take over from here.
 */
export function App(): JSX.Element {
  return (
    <StrictMode>
      <Providers>
        <RouterProvider router={router} />
      </Providers>
    </StrictMode>
  );
}
