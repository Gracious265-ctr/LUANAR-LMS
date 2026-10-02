# UI Context — LUANAR Leave Management System

## 1. Design Direction

The LUANAR Leave Management System must use a professional, minimal, and user-friendly visual language aligned with the LUANAR institutional identity.

The primary visual identity must be based on:

- White as the dominant surface color.
- LUANAR blue as the primary brand and interaction color.
- Institutional green as a secondary semantic color, primarily for successful and approved states.
- Neutral slate tones for text, borders, backgrounds, and supporting UI.
- Minimal animation.
- Spacious layouts and clear visual hierarchy.
- Clean card-based dashboard patterns.
- Consistent use of semantic design tokens.

The attached dashboard reference establishes the **layout pattern only**. Do not copy its e-commerce content, labels, metrics, or business concepts.

The system must feel like an institutional application rather than a commercial e-commerce dashboard.

---

# 2. Color Tokens

## Brand and Primary

| Token | Hex | Usage |
|---|---|---|
| `brand-primary` | `#0097F0` | Primary LUANAR brand color, primary buttons, active navigation, links |
| `brand-primary-hover` | `#0088D8` | Hover state for primary controls |
| `brand-primary-active` | `#0079C0` | Pressed/active state |
| `brand-primary-subtle` | `#EFF8FF` | Selected navigation, highlighted cards, soft backgrounds |
| `brand-primary-muted` | `#DDF1FC` | Secondary highlights and selected states |
| `brand-primary-border` | `#B8E1F8` | Borders around primary-themed elements |
| `brand-primary-foreground` | `#FFFFFF` | Text/icons placed directly on primary blue |

## Institutional Secondary

| Token | Hex | Usage |
|---|---|---|
| `brand-secondary` | `#009119` | Institutional green; success and approved states |
| `brand-secondary-hover` | `#007A16` | Hover state |
| `brand-secondary-subtle` | `#EFFBF1` | Soft success/approved backgrounds |
| `brand-secondary-muted` | `#DDF5E1` | Secondary success highlights |
| `brand-secondary-border` | `#B8E5BF` | Success/approved borders |
| `brand-secondary-foreground` | `#FFFFFF` | Text/icons placed directly on green |

## Neutral Surfaces

| Token | Hex | Usage |
|---|---|---|
| `surface-page` | `#F8FAFC` | Main application background |
| `surface-card` | `#FFFFFF` | Cards, panels, forms, modals |
| `surface-elevated` | `#FFFFFF` | Dropdowns, popovers, dialogs |
| `surface-muted` | `#F1F5F9` | Secondary sections and muted containers |
| `surface-subtle` | `#F8FAFC` | Very subtle backgrounds |
| `surface-hover` | `#F1F5F9` | Hover background for neutral elements |
| `surface-active` | `#E8EEF5` | Pressed/active neutral state |
| `surface-disabled` | `#F1F5F9` | Disabled controls |

## Text

| Token | Hex | Usage |
|---|---|---|
| `text-primary` | `#0F172A` | Headings and primary content |
| `text-secondary` | `#475569` | Supporting text, descriptions, labels |
| `text-muted` | `#64748B` | Metadata, timestamps, secondary information |
| `text-placeholder` | `#94A3B8` | Input placeholders |
| `text-disabled` | `#CBD5E1` | Disabled text |
| `text-on-brand` | `#FFFFFF` | Text on blue/green backgrounds |
| `text-link` | `#0079C0` | Links and interactive text |
| `text-link-hover` | `#00679F` | Hovered links |

## Borders and Dividers

| Token | Hex | Usage |
|---|---|---|
| `border-default` | `#E2E8F0` | Standard cards, inputs, panels |
| `border-subtle` | `#EEF2F6` | Very light dividers |
| `border-strong` | `#CBD5E1` | Inputs and controls requiring stronger definition |
| `border-focus` | `#0097F0` | Keyboard focus and active form fields |
| `border-error` | `#FCA5A5` | Invalid/destructive input state |
| `border-success` | `#86D69A` | Valid/approved state |
| `border-warning` | `#FCD34D` | Warning state |

---

# 3. Semantic Status Colors

| Token | Hex | Usage |
|---|---|---|
| `status-pending` | `#D97706` | Pending review, awaiting action |
| `status-pending-subtle` | `#FFF7E6` | Pending status background |
| `status-approved` | `#009119` | Approved applications and successful operations |
| `status-approved-subtle` | `#EFFBF1` | Approved status background |
| `status-rejected` | `#DC2626` | Rejected applications |
| `status-rejected-subtle` | `#FEF2F2` | Rejected status background |
| `status-correction` | `#7C3AED` | Correction required |
| `status-correction-subtle` | `#F5F3FF` | Correction-required background |
| `status-cancelled` | `#64748B` | Cancelled applications |
| `status-cancelled-subtle` | `#F1F5F9` | Cancelled status background |
| `status-info` | `#0097F0` | Informational messages |
| `status-info-subtle` | `#EFF8FF` | Informational background |

---

# 4. Form and Interaction Tokens

| Token | Hex | Usage |
|---|---|---|
| `input-background` | `#FFFFFF` | Input fields |
| `input-border` | `#CBD5E1` | Default input border |
| `input-border-hover` | `#94A3B8` | Hovered input |
| `input-border-focus` | `#0097F0` | Focused input |
| `input-ring-focus` | `#0097F033` | Accessible focus ring |
| `input-disabled` | `#F1F5F9` | Disabled input background |
| `button-primary` | `#0097F0` | Primary action |
| `button-primary-hover` | `#0088D8` | Primary action hover |
| `button-secondary` | `#FFFFFF` | Secondary action |
| `button-secondary-hover` | `#F1F5F9` | Secondary action hover |
| `button-destructive` | `#DC2626` | Destructive actions |
| `button-destructive-hover` | `#B91C1C` | Destructive hover |

---

# 5. Accent Colors

Accents must distinguish different information types without competing with the LUANAR primary blue.

| Token | Base | Subtle Background | Usage |
|---|---|---|---|
| `accent-blue` | `#0097F0` | `#EFF8FF` | Information and primary actions |
| `accent-green` | `#009119` | `#EFFBF1` | Approved and successful states |
| `accent-orange` | `#D97706` | `#FFF7E6` | Pending and attention states |
| `accent-red` | `#DC2626` | `#FEF2F2` | Rejected and destructive states |
| `accent-purple` | `#7C3AED` | `#F5F3FF` | Correction-required states |
| `accent-slate` | `#64748B` | `#F1F5F9` | Neutral, cancelled, or inactive states |

---

# 6. AI Accent

The core LUANAR Leave Management System does not currently require AI functionality.

If AI-assisted functionality is introduced later, it must remain visually distinct from the institutional workflow while preserving the LUANAR visual identity.

| Token | Hex | Usage |
|---|---|---|
| `ai-primary` | `#7C3AED` | AI-generated or AI-assisted features |
| `ai-subtle` | `#F5F3FF` | AI feature backgrounds |
| `ai-border` | `#DDD6FE` | AI feature borders |
| `ai-foreground` | `#FFFFFF` | Text/icons on AI accent |

---

# 7. Typography

## Typography Tokens

| Token | Value | Usage |
|---|---|---|
| `font-family-primary` | `Geist, ui-sans-serif, system-ui, sans-serif` | Entire application |
| `font-family-mono` | `Geist Mono, ui-monospace, monospace` | Reference numbers and technical identifiers |
| `text-xs` | `12px / 18px` | Metadata, timestamps, compact labels |
| `text-sm` | `14px / 20px` | Form labels, secondary text, table content |
| `text-base` | `16px / 24px` | Default body text |
| `text-lg` | `18px / 28px` | Card headings and emphasized content |
| `text-xl` | `20px / 28px` | Section headings |
| `text-2xl` | `24px / 32px` | Page section headings |
| `text-3xl` | `30px / 36px` | Main dashboard/page headings |
| `text-4xl` | `36px / 40px` | Large dashboard metrics |
| `font-normal` | `400` | Body text |
| `font-medium` | `500` | Labels, navigation, supporting headings |
| `font-semibold` | `600` | Card headings and important values |
| `font-bold` | `700` | Main page headings and major metrics |
| `leading-body` | `1.5` | Paragraph text |
| `leading-tight` | `1.2` | Headings and display sizes |

## Typography Rules

- Use Geist Sans throughout the application.
- Use Geist Mono for reference numbers and technical identifiers.
- Use `font-semibold` or `font-bold` for primary page headings.
- Use `font-normal` for normal body content.
- Use `font-medium` for labels and navigation.
- Use `font-semibold` for important values and card headings.
- Establish hierarchy through typography, spacing, and semantic color.
- Do not introduce additional fonts without an explicit design decision.
- Do not use excessive font weights.
- Avoid compressed line heights that reduce readability.
- Allow long text to wrap naturally.
- Body copy is 14px and runs at 1.5; headings run at 1.2. Do not compress below
  those, and do not use 13px for captions -- 12px is the caption size.

---

# 8. Border Radius

The scale is deliberately flat: a single 6px geometry for anything a person
touches, a 4px step for dense labels, and a true circle for circles. A second
larger radius existed before and was removed -- it made the app read as softer
and rounder than the product is, and every call site now resolves to 6px
without changing.

| Token | Value | Usage |
|---|---:|---|
| `radius-xs` | `4px` | Status labels and small text chips |
| `radius-sm` | `4px` | Badges, status pills, calendar day cells |
| `radius-md` | `6px` | Buttons, inputs, selects, checkboxes |
| `radius-lg` | `6px` | Cards, dropdowns, dialogs (aliases `radius-md`) |
| `radius-xl` | `6px` | Dashboard panels (aliases `radius-md`) |
| `radius-2xl` | `6px` | Modals (aliases `radius-md`) |
| `radius-3xl` | `6px` | Feature containers (aliases `radius-md`) |
| `radius-4xl` | `6px` | Large sections (aliases `radius-md`) |
| `radius-full` | `9999px` | Avatars, circular icon tiles, scrollbars, toggle tracks |
| `control-radius` | `6px` | The one radius for any control surface |

`radius-lg` through `radius-4xl` are kept as aliases so existing call sites keep
resolving, but they all mean 6px. Adding a new larger radius requires a
deliberate decision, not a default.

## Component Radius Rules

| Component | Radius |
|---|---|
| Buttons | `control-radius` (6px) |
| Inputs | `control-radius` (6px) |
| Selects | `control-radius` (6px) |
| Checkboxes | `control-radius` (6px) |
| Badges | `radius-sm` (4px) |
| Status pills | `radius-sm` (4px) |
| Cards | `radius-lg` (6px) |
| Dashboard panels | `radius-xl` (6px) |
| Modals | `radius-2xl` (6px) |
| Drawer | `radius-none` on the anchored edge, `radius-lg` on the free edge |
| Avatars | `radius-full` |
| Icon containers | `radius-full` when circular, otherwise 6px |
| Scrollbars, progress tracks, switch tracks | `radius-full` |

Status is a label, not a control, so it uses 4px. That is what stops a row of
badges from competing with the real buttons beside it.

---

# 9. Shadows

The philosophy is **border-first**. A static element's edge is a real 1px
`border`, not a shadow. True `box-shadow` is reserved for three situations: a
state change (hover), an element that must appear above the page plane (a
popover), and a modal. Everything else stays flat.

| Token | Value | Usage |
|---|---|---|
| `shadow-none` | `none` | Flat elements |
| `shadow-subtle` | `0 1px 2px #0000000d` | Soft lift on bordered surfaces |
| `shadow-card` | `0 1px 2px #0000000d` | Cards and static containers |
| `shadow-hover` | `0 0 0 1px #0000001a, 0 4px 12px #00000014` | Interactive hover only |
| `shadow-dropdown` | `0 4px 4px #0000000d` | Dropdowns, popovers, tooltips, selects |
| `shadow-modal` | `0 8px 16px -4px #0000000d, 0 24px 32px -8px #0000001a` | Dialogs, drawers, alerts |
| `shadow-focus` | `0 0 0 2px #ffffff, 0 0 0 4px #0097f0` | Every focused control |
| `shadow-pressed` | `inset 0 1px 1px #0000000d` | Active/pressed controls |

The shadcn `shadow-2xs` through `shadow-2xl` names are aliased onto these.
`sm` and `md` map *down* to the card depth, because the shadcn names imply a
heavier treatment than the same surface receives here.

## Focus

Focus is a single shared treatment, applied via the `focus-ring` utility in
`app/globals.css`, and it is keyboard-only (`:focus-visible`). Every control --
button, input, select, checkbox -- uses it, so a focused field is recognisable
as the same ring everywhere.

The ring is a two-layer box shadow: an opaque white ring to separate the
indicator from the control, then the LUANAR blue ring outside it. A
`ring-offset` approach is deliberately not used: offset colour breaks on
transparent and gradient parents, and the white inner ring does not. Invalid
fields get the same two layers in `--status-rejected` red.

## Stacking

Overlays are grouped by role so a popover can never render under a dialog, and
a modal is never opened from inside a menu.

| Token | Value | Used by |
|---|---:|---|
| `z-index-base` | `0` | Default |
| `z-index-raised` | `1` | Card content above its own surface |
| `z-index-header` | `75` | Sticky header |
| `z-index-popover` | `100` | Popovers, tooltips, and select menus on a plain page |
| `z-index-modal-overlay` | `1000` | Dialog and alert-dialog backdrop |
| `z-index-modal` | `1010` | Dialog, alert-dialog and drawer content |
| `z-index-portal-above` | `1100` | Select menus, popovers, tooltips and alert dialogs opened *from inside* a dialog |
| `z-index-toast` | `1200` | Toasts, which must be readable over a dialog |

Use these names (`z-modal`, `z-modal-overlay`, `z-portal-above`, `z-toast`)
rather than bare `z-50`.

`z-portal-above` exists because Radix portals to `<body>`, so a select menu
inside a dialog is a *sibling* of the dialog rather than a descendant. A single
`z-modal` value for both the backdrop and the content cannot express "above this
dialog", and a control rendered under the dialog is unusable, not merely
misaligned. Any primitive that can open from within a dialog — select, popover,
tooltip, alert dialog — uses `z-portal-above`; a `z-popover` menu is only ever
correct when there is no modal on the page.

---

# 10. Layout and Visual Direction

| Property | Standard |
|---|---|
| Page background | `surface-page` |
| Card background | `surface-card` |
| Primary brand | `brand-primary` |
| Success/approved | `brand-secondary` |
| Main text | `text-primary` |
| Secondary text | `text-secondary` |
| Borders | `border-default` |
| Dashboard style | Clean, spacious, card-based |
| Navigation | Collapsible sidebar rail on desktop; hamburger + drawer below `md` |
| Active navigation | LUANAR blue |
| Cards | White surfaces with subtle borders/shadows |
| Visual density | Moderate whitespace |
| Animation | Minimal and purposeful, `200ms` ease-out |
| Touch targets | 44px minimum below `md`, except actions inside a scrolling table |
| Normal transition | `200ms` (`duration-base`) |
| Large animations | Prohibited unless required for meaningful interaction |
| Gradients | Prohibited for ordinary UI surfaces |
| Glassmorphism | Prohibited |
| Excessive shadows | Prohibited |
| Primary actions | LUANAR blue |
| Approved states | Institutional green |
| Destructive states | Red |
| Pending states | Orange |
| Correction states | Purple |

---

# 10a. Breakpoints and the Mobile Drawer

| Token | Value | Meaning |
|---|---:|---|
| `sm` | `600px` | Two-up forms and stacked-to-row controls |
| `md` | `960px` | Two-column forms, table-vs-card switch, drawer boundary |
| `lg` | `1024px` | Genuine third column and desktop-only panes |

`sm` and `md` were moved out from Tailwind's 640px and 768px defaults. The data
tables in this app are dense enough that a tablet in landscape is still a
phone-sized reading experience, so the two-column and table/card switches wait
until 960px. `lg` is deliberately left at 1024px: 27 call sites depend on the
current value, and the layouts that need a real third column are desktop-only.

**Navigation below `md`.** The rail is removed from the DOM flow and replaced by
a hamburger in the header that opens a Radix `Dialog` drawer. Both surfaces
render the same `NavLinks` list, so a route can never exist in one and not the
other. The drawer is dialog-based on purpose: focus trap, Escape to dismiss,
`aria-modal`, and body scroll lock are the behaviours a slide-out menu owes its
user, and a modal primitive already solves all of them.

The two pieces of state are independent. `sidebarOpen` is the desktop rail's
collapsed state; `drawerOpen` is whether the phone overlay is showing. Collapsing
the rail must not close a drawer, and opening a drawer must not un-collapse a rail
the user left collapsed.

`useIsMobile` returns `false` until mounted, because the server has no viewport
to measure. The desktop layout therefore renders for the first paint; rendering
mobile on the server and swapping on hydration would flash the wrong shell and
re-run every layout effect.

**Touch targets.** Below `md`, buttons, links acting as buttons, and text
inputs, selects and textareas grow to a 44px minimum height. The exception is
controls inside `.overflow-x-auto`: those tables are desktop-density layouts
read sideways on a phone, and growing their actions would triple the row height.
Mark a genuinely dense control `data-dense` to opt out explicitly.

---

# 11. Iconography

| Property | Standard |
|---|---|
| Icon library | Lucide React |
| Default icon size | `18px` |
| Small icon size | `16px` |
| Large icon size | `20–24px` |
| Stroke width | Use Lucide defaults |
| Icon color | Inherit semantic text/state color |
| Custom SVG icons | Do not create when an equivalent Lucide icon exists |
| Decorative icons | Do not use without a clear purpose |
| Logo | Use the official LUANAR logo asset |

---

# 12. 21st.dev Component Library

The project uses **21st.dev** as the primary component-library source.

| Rule | Standard |
|---|---|
| Component foundation | 21st.dev |
| Existing components | Reuse before creating an equivalent |
| Customization | Use props, composition, variants, and project tokens |
| Business logic | Must remain outside reusable UI components |
| Styling | Must use the project's semantic design tokens |
| Accessibility | Must be preserved |
| Duplication | Do not create duplicate components |
| Shared components | Keep reusable components in the shared component structure |

Do not replace 21st.dev components with shadcn/ui components unless the project architecture is explicitly changed and documented.

---

# 13. Theme Tokens

| Token | Light Theme |
|---|---|
| `theme-background` | `surface-page` |
| `theme-foreground` | `text-primary` |
| `theme-card` | `surface-card` |
| `theme-card-foreground` | `text-primary` |
| `theme-primary` | `brand-primary` |
| `theme-primary-foreground` | `brand-primary-foreground` |
| `theme-secondary` | `surface-muted` |
| `theme-secondary-foreground` | `text-secondary` |
| `theme-muted` | `surface-muted` |
| `theme-muted-foreground` | `text-muted` |
| `theme-border` | `border-default` |
| `theme-input` | `input-border` |
| `theme-ring` | `border-focus` |
| `theme-destructive` | `button-destructive` |
| `theme-destructive-foreground` | `#FFFFFF` |

---

# 14. Design Principles

| Principle | Rule |
|---|---|
| Institutional identity | Use LUANAR blue as the dominant brand and interaction color |
| Professionalism | Use clean white surfaces, restrained borders, subtle shadows, and generous spacing |
| Minimalism | Avoid unnecessary decoration and visual noise |
| Clarity | Make application status, approval stage, balance, and required actions immediately understandable |
| Consistency | Reuse the same semantic tokens and component patterns throughout the application |
| Accessibility | Maintain sufficient contrast and visible keyboard focus |
| Hierarchy | Use typography, spacing, and semantic color to establish hierarchy |
| Feedback | Use subtle animation and clear semantic colors to communicate state changes |
| Trust | Keep important leave information visually stable and predictable |
| Animation | Use animation to communicate interaction or state, not as decoration |

---

# 15. Core Visual Direction

The application's visual system must follow this hierarchy:

**White → LUANAR Blue → Institutional Green → Neutral Slate → Semantic Accents**

Use LUANAR blue as the dominant interactive color.

Use institutional green primarily for:

- Approved leave.
- Successful operations.
- Positive confirmations.
- Successful completion states.

Use semantic accents only when they communicate a meaningful state.

The interface must remain predominantly white and neutral, with blue providing identity and interaction emphasis rather than covering large portions of the interface.

The final visual character must be:

**Professional + Institutional + Minimal + Clear + Approachable**

