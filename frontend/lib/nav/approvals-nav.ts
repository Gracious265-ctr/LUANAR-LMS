import type { ComponentType } from "react";

import { ClipboardCheck, UserCheck } from "lucide-react";

/**
 * The Approvals module's own navigation.
 *
 * This is the approver's side of leave: the queue of applications waiting on a
 * decision, and their own request to be covered while away. Reached from the
 * institutional rail's "Approvals" entry, it is the one place those two
 * destinations live, so the approver never has to read past the HR folio and
 * their personal destinations to act on a request.
 *
 * Follows the shape the Leave, Plans, Leave-Configuration, Organisation, and
 * Documents modules established — an item list plus a boundary predicate — so
 * the shell only learns one module-scoping pattern.
 */
export type ApprovalsNavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** Whether `pathname` should mark this item as the active page. */
  match: (pathname: string) => boolean;
  /** A count to surface beside the item, e.g. decisions waiting on the caller. */
  badge?: number;
};

const QUEUE_ROOT = "/dashboard/approvals";
const COVER_ROOT = "/dashboard/cover";

/** Whether `pathname` is `root` itself or something beneath it. */
function under(pathname: string, root: string): boolean {
  return pathname === root || pathname.startsWith(`${root}/`);
}

/**
 * `true` when `pathname` belongs to the Approvals module.
 *
 * Both the queue at ``/dashboard/approvals`` and the approver's own cover
 * requests at ``/dashboard/cover`` are the same module — they are the two acts
 * an approver performs around a leave request — so either shows the module rail.
 */
export function isApprovalsModule(pathname: string): boolean {
  return under(pathname, QUEUE_ROOT) || under(pathname, COVER_ROOT);
}

const QUEUE_ITEM: ApprovalsNavItem = {
  label: "Approvals",
  href: QUEUE_ROOT,
  icon: ClipboardCheck,
  match: (pathname) => under(pathname, QUEUE_ROOT),
};

const COVER_ITEM: ApprovalsNavItem = {
  label: "Request Cover",
  href: COVER_ROOT,
  icon: UserCheck,
  match: (pathname) => under(pathname, COVER_ROOT),
};

/**
 * The module's rail for this viewer: the queue everyone in the module can act
 * on, and their own cover requests.
 *
 * `pendingApprovals` is the count the layout already resolved, so the queue
 * item carries the same badge it does in the institutional rail.
 */
export function approvalsNavItems({
  pendingApprovals,
  canRequestCover,
}: {
  pendingApprovals: number;
  canRequestCover: boolean;
}): ApprovalsNavItem[] {
  const items: ApprovalsNavItem[] = [
    { ...QUEUE_ITEM, badge: pendingApprovals },
  ];
  if (canRequestCover) {
    items.push(COVER_ITEM);
  }
  return items;
}
