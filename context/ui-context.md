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
| `font-family-primary` | `Inter, ui-sans-serif, system-ui, sans-serif` | Entire application |
| `font-family-mono` | `ui-monospace, SFMono-Regular, Menlo, monospace` | Reference numbers and technical identifiers |
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

## Typography Rules

- Use Inter throughout the application.
- Use `font-semibold` or `font-bold` for primary page headings.
- Use `font-normal` for normal body content.
- Use `font-medium` for labels and navigation.
- Use `font-semibold` for important values and card headings.
- Establish hierarchy through typography, spacing, and semantic color.
- Do not introduce additional fonts without an explicit design decision.
- Do not use excessive font weights.
- Avoid compressed line heights that reduce readability.
- Allow long text to wrap naturally.

---

# 8. Border Radius

| Token | Value | Usage |
|---|---:|---|
| `radius-sm` | `6px` | Small controls and badges |
| `radius-md` | `8px` | Inputs and buttons |
| `radius-lg` | `12px` | Larger controls and dropdowns |
| `radius-xl` | `16px` | Cards and dashboard panels |
| `radius-2xl` | `20px` | Large cards and prominent sections |
| `radius-3xl` | `24px` | Modals and large feature containers |
| `radius-full` | `9999px` | Avatars, pills, circular controls |

## Component Radius Rules

| Component | Radius |
|---|---|
| Buttons | `radius-md` |
| Inputs | `radius-md` |
| Selects | `radius-md` |
| Badges | `radius-sm` or `radius-full` |
| Status pills | `radius-full` |
| Cards | `radius-xl` |
| Dashboard panels | `radius-xl` |
| Modals | `radius-2xl` |
| Avatars | `radius-full` |
| Icon containers | `radius-lg` |

---

# 9. Shadows

The interface must remain predominantly flat and clean. Shadows must provide hierarchy rather than decoration.

| Token | Value | Usage |
|---|---|---|
| `shadow-none` | `none` | Flat elements |
| `shadow-subtle` | `0 1px 2px rgba(15, 23, 42, 0.04)` | Cards and containers |
| `shadow-card` | `0 2px 8px rgba(15, 23, 42, 0.06)` | Elevated cards |
| `shadow-dropdown` | `0 8px 24px rgba(15, 23, 42, 0.10)` | Dropdowns and popovers |
| `shadow-modal` | `0 16px 40px rgba(15, 23, 42, 0.14)` | Dialogs and modals |

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
| Navigation | Persistent sidebar with clear active state |
| Active navigation | LUANAR blue |
| Cards | White surfaces with subtle borders/shadows |
| Visual density | Moderate whitespace |
| Animation | Minimal and purposeful |
| Normal transition | `150–250ms` |
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

