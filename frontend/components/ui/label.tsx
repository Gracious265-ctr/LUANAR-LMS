import * as LabelPrimitive from "@radix-ui/react-label";

import { cn } from "@/lib/utils";

/**
 * Form label. Matches the weight and colour `Field` has always used so a
 * label renders identically whether it is composed here or inline.
 */
export function Label({
  className,
  ...props
}: React.ComponentPropsWithRef<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        "text-sm font-medium leading-none text-text-secondary select-none block mb-2",
        "peer-disabled:cursor-not-allowed peer-disabled:opacity-60",
        "group-data-[disabled=true]:pointer-events-none",
        className
      )}
      {...props}
    />
  );
}
