"use client";

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { CheckIcon, MinusIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Tri-state checkbox.
 *
 * Renders a `<button role="checkbox">` with `aria-checked`, so `toBeChecked()`
 * and `getByLabelText` keep working; only `element.checked` does not.
 */
export function Checkbox({
  className,
  ...props
}: React.ComponentPropsWithRef<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer size-5 shrink-0 rounded-control border border-input-border bg-input-background",
        "transition-[background-color,border-color,box-shadow] duration-base ease-standard",
        "focus-visible:border-input-border-focus focus-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-[invalid=true]:border-border-error",
        "data-[state=checked]:border-transparent data-[state=checked]:bg-button-primary data-[state=checked]:text-button-primary-foreground",
        "data-[state=indeterminate]:border-transparent data-[state=indeterminate]:bg-button-primary data-[state=indeterminate]:text-button-primary-foreground",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="flex items-center justify-center text-current"
      >
        {props.checked === "indeterminate" ? (
          <MinusIcon className="size-3.5" />
        ) : (
          <CheckIcon className="size-3.5" />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}
