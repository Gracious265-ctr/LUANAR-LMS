import { cn } from "@/lib/utils";

import { fieldStyles } from "./input";

export function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(fieldStyles, className)} {...props} />;
}
