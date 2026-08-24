/// <reference types="vite/client" />

/**
 * Build-time configuration.
 *
 * Declared rather than left to vite/client's index signature so `tsc -b` fails
 * on a typo instead of silently handing back `undefined` at runtime, which
 * would look exactly like an unset variable.
 */
interface ImportMetaEnv {
  /**
   * Where the API lives. Unset means `/api`, which the dev proxy forwards.
   *
   * Deployed, this is the backend's **origin root with no `/api` suffix** --
   * `https://api.example.com`, not `https://api.example.com/api`. The dev
   * proxy strips the prefix (web/vite.config.ts) and the backend's own routes
   * are unprefixed, so a value carrying `/api` produces a uniform 404 against
   * a completely healthy backend, which is a miserable thing to debug.
   */
  readonly VITE_API_BASE?: string;

  /**
   * "1" builds the standalone demo: no backend, no network calls, fixtures
   * from a real finished run compiled into the bundle. See src/api/demo.ts.
   */
  readonly VITE_DEMO_MODE?: string;

  /**
   * Optional contact address shown on the landing page and in demo mode, where
   * there is no backend to accept an access request. Unset, the page points at
   * the GitHub repository instead -- publishing an address is a decision for
   * whoever owns it, not a default.
   */
  readonly VITE_CONTACT_EMAIL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
