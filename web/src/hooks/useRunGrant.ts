import { useEffect, useState } from "react";
import { runGrant } from "../api/client";

/**
 * The URL credential for one run's media, or null until it arrives.
 *
 * `<video src>` and download anchors cannot send an Authorization header, so
 * the URL carries a short-lived grant instead. It used to carry the session
 * token, which meant browser history and proxy logs held full account access.
 *
 * Null means "not yet", not "denied". A run with no owner needs no grant at
 * all and its URLs work without one, so a component should render the media
 * regardless and let the request fail on its own if it is going to.
 */
export function useRunGrant(run_id: string | undefined): string | null {
  const [grant, setGrant] = useState<string | null>(null);

  useEffect(() => {
    if (!run_id) return;
    let live = true;
    runGrant(run_id)
      .then((t) => {
        if (live) setGrant(t);
      })
      .catch(() => {
        // Anonymous runs have no owner and issue no grant. Leaving this null
        // is correct: the URL without one still works for them.
        if (live) setGrant(null);
      });
    return () => {
      live = false;
    };
  }, [run_id]);

  return grant;
}
