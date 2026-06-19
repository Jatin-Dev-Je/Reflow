import { createBrowserRouter, Navigate } from "react-router-dom";

import { LoginPage } from "@/features/auth/pages/login-page";
import * as routes from "@/lib/constants/routes";

/**
 * Declarative route tree.
 *
 * Imports each route's page from its feature folder. Pattern for new routes:
 *   { path: routes.X, element: <XPage /> }
 *
 * Layouts go via `element` on a parent route and an <Outlet/> in the layout
 * component. We add lazy-loading per route as the bundle grows.
 */
export const router = createBrowserRouter([
  {
    path: routes.HOME,
    // Until Landing ships, send unauthenticated visitors to /login.
    element: <Navigate to={routes.LOGIN} replace />,
  },
  {
    path: routes.LOGIN,
    element: <LoginPage />,
  },
  // Catch-all → /login (replaced with a real NotFound page later).
  {
    path: "*",
    element: <Navigate to={routes.LOGIN} replace />,
  },
]);
