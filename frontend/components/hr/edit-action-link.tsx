import Link from "next/link";
import { Pencil } from "lucide-react";

export function EditActionLink({ href }: { href: string }) {
  return (
    <Link
      href={href}
      aria-label="Edit"
      title="Edit record"
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-default bg-button-secondary text-text-secondary transition-colors hover:bg-button-secondary-hover hover:text-text-primary"
    >
      <Pencil className="h-4 w-4" />
    </Link>
  );
}