import { NewApplicationClient } from "@/components/leave/NewApplicationClient";

/**
 * "New Application" — the compose flow on its own route so the sidebar item
 * opens the form directly instead of funneling to the drafts list.
 */
export default function NewApplicationPage() {
  return <NewApplicationClient />;
}
