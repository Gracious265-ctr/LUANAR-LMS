"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** Value meaning "open a blank create form" rather than edit an existing row. */
const CREATE = "new";

export interface OverlayParam {
  /**
   * The row id the overlay is editing, or `"new"` for a create form. `null`
   * when the overlay is closed.
   */
  target: string | null;
  isOpen: boolean;
  isCreate: boolean;
  /** Pushes `?<key>=new` without disturbing the host's own query. */
  openCreate: () => void;
  /**
   * Pushes `?<key>=1` for an overlay that has no record to edit — a preview or
   * a confirmation, where the only state is open or shut.
   */
  open: () => void;
  /** Pushes `?<key>=<id>`. */
  openEdit: (id: number | string) => void;
  /**
   * Steps the overlay closed: back through history when we pushed the state,
   * so the browser Back button and the close affordance agree, falling back to
   * a replace for a direct visit to the deep link where there is nothing to pop.
   */
  close: () => void;
  /**
   * The current path with `key` removed, as a full href. Pass to a
   * "clear filters" action so it can reveal a record the host's filters were
   * hiding, without a page reload.
   */
  hrefWithoutParam: string;
}

/**
 * Drives a URL-keyed overlay on a list page.
 *
 * The open target lives in the query string rather than component state, so a
 * refresh reopens the same record and Back steps out of it. `key` is namespaced
 * per record type so a page hosting two overlays — the leave calendar hosts
 * holidays and financial years — can keep both, and so the host's own filters
 * survive opening one.
 */
export function useOverlayParam(key: string): OverlayParam {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const target = searchParams.get(key);

  const query = useCallback(
    (next: string | null) => {
      const params = new URLSearchParams(searchParams);
      if (next === null) {
        params.delete(key);
      } else {
        params.set(key, next);
      }
      const serialised = params.toString();
      return serialised ? `?${serialised}` : "";
    },
    [key, searchParams]
  );

  const openCreate = useCallback(
    () => router.push(`${pathname}${query(CREATE)}`),
    [pathname, query, router]
  );

  const open = useCallback(
    () => router.push(`${pathname}${query("1")}`),
    [pathname, query, router]
  );

  const openEdit = useCallback(
    (id: number | string) => router.push(`${pathname}${query(String(id))}`),
    [pathname, query, router]
  );

  const close = useCallback(() => {
    if (window.history.length > 1) {
      router.back();
      return;
    }
    router.replace(`${pathname}${query(null)}`);
  }, [pathname, query, router]);

  const hrefWithoutParam = `${pathname}${query(null)}`;

  return useMemo(
    () => ({
      target,
      isOpen: target !== null,
      isCreate: target === CREATE,
      openCreate,
      open,
      openEdit,
      close,
      hrefWithoutParam,
    }),
    [target, openCreate, open, openEdit, close, hrefWithoutParam]
  );
}
