import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * Opens a Radix `Select` listbox without choosing anything.
 *
 * Radix opens on `pointerdown`, so a bare `element.click()` is not enough;
 * this goes through `userEvent` to dispatch the real pointer sequence.
 */
export async function openSelect(
  trigger: HTMLElement,
  options: { user?: ReturnType<typeof userEvent.setup> } = {}
) {
  const user = options.user ?? userEvent.setup();
  await user.click(trigger);
  return user;
}

/**
 * Drives a Radix `Select`.
 *
 * A Radix trigger is a `<button role="combobox">`, not a `<select>`, so the
 * usual `fireEvent.change`, `.options` and `toHaveValue` assertions do not
 * apply to it. Open the trigger, then activate the option by its visible
 * text; the trigger's text content becomes the selected value.
 *
 * `scope` narrows the option lookup for selects rendered inside a dialog.
 */
export async function selectOption(
  trigger: HTMLElement,
  optionName: string | RegExp,
  options: { user?: ReturnType<typeof userEvent.setup>; scope?: HTMLElement } = {}
) {
  const user = options.user ?? userEvent.setup();
  const within_ = options.scope ? within(options.scope) : screen;

  await openSelect(trigger, { user });

  const option = await within_.findByRole("option", { name: optionName });
  await user.click(option);
}

/** Reads the currently selected option out of a Radix `Select` trigger. */
export function selectedValue(trigger: HTMLElement): string {
  return trigger.textContent?.trim() ?? "";
}
