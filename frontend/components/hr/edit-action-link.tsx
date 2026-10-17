import Link from "next/link";
import { Pencil } from "lucide-react";

const EDIT_BUTTON_STYLES =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-default bg-button-secondary text-text-secondary transition-colors hover:bg-button-secondary-hover hover:text-text-primary";

export function EditActionLink({ href }: { href: string }) {
  return (
    <Link
      href={href}
      aria-label="Edit"
      title="Edit record"
      className={EDIT_BUTTON_STYLES}
    >
      <Pencil className="h-4 w-4" />
    </Link>
  );
}

/**
 * The icon-only edit affordance as a button, for tables whose row opens an
 * overlay instead of navigating. Mirrors `EditActionLink`'s chrome exactly so
 * the two are indistinguishable at rest.
 *
 * `label` is a real description rather than a bare "Edit" because these tables
 * render one of these per row: without the record name, a screen reader user
 * hears the same control repeated for every row with no way to tell them apart.
 */
export function EditIconButton({
  onClick,
  label,
}: {
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={EDIT_BUTTON_STYLES}
    >
      <Pencil className="h-4 w-4" />
    </button>
  );
}
