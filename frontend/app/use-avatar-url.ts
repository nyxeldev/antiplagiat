import { useEffect, useState } from "react";
import type { User } from "./account-shell";

/** A plain <img src="/api/auth/avatar/{id}"> cannot carry the
 * X-Antiplagiat-Local header the proxy requires on every route (the browser
 * sends no custom headers for an <img> request), so it gets a 403 from
 * lib/proxy.ts. Fetching it ourselves with that header and handing the
 * <img> a blob: URL instead is the only way to show it without loosening
 * that check for this one route. A separate module from account-shell.tsx
 * so AppShell (which account-shell.tsx itself renders) can import it
 * without a circular import. */
export function useAvatarUrl(user: Pick<User, "id" | "has_avatar" | "avatar_version"> | null) {
  const hasAvatar = !!user?.has_avatar;
  const userId = user?.id;
  const avatarVersion = user?.avatar_version ?? 0;
  const [fetchedUrl, setFetchedUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!hasAvatar || !userId) return; // nothing to fetch -- the hook returns null for this case below, without touching state here
    let cancelled = false; let objectUrl: string | null = null;
    fetch(`/api/auth/avatar/${userId}?v=${avatarVersion}`, { headers: { "X-Antiplagiat-Local": "1" }, cache: "no-store" })
      .then(r => (r.ok ? r.blob() : null))
      .then(blob => { if (cancelled || !blob) return; objectUrl = URL.createObjectURL(blob); setFetchedUrl(objectUrl); })
      .catch(() => {});
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [userId, hasAvatar, avatarVersion]);
  return hasAvatar ? fetchedUrl : null;
}
