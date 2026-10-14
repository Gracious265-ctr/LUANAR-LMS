analyzing https://stripe.com/ ...
analyze: cache hit (14:28 UTC)
generating DESIGN.md ...
---
name: Stripe
url: https://stripe.com/
colors:
  primary: '#533afd'
  primary-hover: '#665efd' # from --hds-color-input-border-hover
  primary-active: '#4236cc' # inferred from screenshot
  background: '#ffffff'
  background-subtle: '#f8fafd'
  background-accent: '#e5edf5'
  text-primary: '#000000'
  text-heading: '#061b31'
  text-secondary: '#50617a'
  text-muted: '#64748d'
  text-input-label: '#273951'
  text-placeholder: '#7d8ba4'
  text-inverse: '#ffffff'
  border: '#e5edf5' # inferred from screenshot
  border-subtle: '#a8c3de4d' # from --hds-color-core-neutral-50A
  accent-orange: '#ff6118'
  accent-peach: '#ffe0d1'
  accent-lavender: '#e2e4ff'
  accent-success: '#00d66f'
  dark-background: '#000000'
  dark-surface: '#0d1738' # from --hds-color-core-neutralDark-990
  dark-surface-hover: '#1a3a5c' # from rgb(26, 58, 92)
  dark-text: '#ffffff'
  dark-text-muted: '#7d8ba4' # from --hds-color-input-text-placeholder
typography:
  family-primary: 'sohne-var, ui-sans-serif, system-ui, sans-serif'
  family-monospace: 'SFMono-Regular, Consolas, Liberation Mono, Menlo, monospace' # inferred
  display:
    family: 'sohne-var'
    size: 40px
    weight: 700
    line-height: 1.2
  heading-lg:
    family: 'sohne-var'
    size: 32px
    weight: 700
    line-height: 1.2
  heading-md:
    family: 'sohne-var'
    size: 26px
    weight: 700
    line-height: 1.2
  heading-sm:
    family: 'sohne-var'
    size: 22px
    weight: 400
    line-height: 1.5
  body:
    family: 'sohne-var'
    size: 16px
    weight: 400
    line-height: 1.5
  caption:
    family: 'sohne-var'
    size: 14px
    weight: 400
    line-height: 1.3
  small:
    family: 'sohne-var'
    size: 10px
    weight: 400
    line-height: 1.2
spacing:
  base: 4px
  scale: [0, 4, 8, 12, 16, 20, 24, 32]
radius:
  xs: 3px
  sm: 4px
  md: 6px
  lg: 8px
  full: 100px
elevation:
  card: '0px 3px 6px rgba(23, 23, 23, 0.06)' # from shadows[2]
  hover: '0px 15px 35px rgba(23, 23, 23, 0.08)' # from shadows[1]
  modal: '0px 16px 32px rgba(50, 50, 93, 0.12)' # from shadows[0]
  z-negative: -1
  z-base: 1
  z-navigation: 2
  z-dialog: 3
  z-feature: 4
  z-chat: 99
  z-notification: 9999
  z-iframe: 2147483639
motion:
  duration-fast: '0.1s'
  duration-base: '0.2s'
  duration-medium: '0.3s'
  duration-long: '0.75s'
  easing-standard: 'cubic-bezier(0.33, 1, 0.68, 1)'
  easing-ease-out: 'cubic-bezier(0.25, 1, 0.5, 1)' # inferred
components:
  button-primary:
    bg: '{colors.primary}'
    text: '{colors.text-inverse}'
    radius: '{radius.sm}'
    padding: '16px 24px' # from extracted button "Démarrer maintenant"
  button-secondary:
    bg: '{colors.background-accent}'
    text: '{colors.text-heading}'
    radius: '{radius.sm}'
    padding: '12px 20px' # inferred from screenshot
  button-ghost:
    bg: 'transparent'
    text: '{colors.primary}'
    radius: '{radius.sm}'
    padding: '12px 20px' # inferred from screenshot
  card:
    bg: '{colors.background}'
    radius: '{radius.md}'
    shadow: '{elevation.card}'
  input:
    bg: '{colors.background}'
    border: '{colors.border}'
    text: '{colors.text-heading}'
    radius: '{radius.sm}'
    padding: '12px 16px'
---

# Design System Inspired by Stripe

## 1. Visual Theme & Atmosphere
Stripe's design system exudes a sophisticated yet approachable aesthetic, characterized by a clean layout and strategic use of vibrant gradients. The primary typeface, `sohne-var`, is consistently applied across all text elements, providing a modern and highly legible foundation. Key visual elements include dynamic, flowing gradients, such as the prominent orange-pink-purple blend (`#ff6118` to `#ea2261` to `#533afd` inferred) that serves as a backdrop for hero sections and product illustrations, creating a sense of depth and energy. Subtle CSS animations enhance interactivity, particularly on navigation elements and card hovers, contributing to a polished user experience.

The atmosphere is one of technological precision and forward-thinking innovation, achieved through a balanced interplay of crisp typography, ample whitespace, and carefully chosen accent colors. Illustrations are abstract and geometric, often incorporating the brand's gradient palette, reinforcing a cohesive digital identity. The overall impression is professional and trustworthy, guiding users through complex financial services with clarity and visual appeal.

**Key Characteristics**
*   **Primary Typeface**: `sohne-var` for all text.
*   **Brand Gradient**: Dynamic orange-pink-purple visual flow.
*   **Primary Color**: `#533afd` for key actions.
*   **Whitespace**: Generous padding and margins for clarity.
*   **Subtle Animation**: CSS keyframe animations for interactive elements.
*   **Abstract Illustrations**: Geometric shapes with gradient fills.
*   **Clean Layout**: Uncluttered presentation of complex information.

## 2. Color Palette & Roles
Stripe's color palette is a blend of professional neutrals and vibrant accents, anchored by a distinct brand blue.

-   **Primary**: `#533afd` — The core brand color, used for primary calls-to-action, active states, and key interactive elements.
-   **Primary Hover**: `#665efd` — A slightly lighter shade of blue, used for hover states on interactive elements to provide visual feedback.
-   **Primary Active**: `#4236cc` (inferred from screenshot) — A darker, more saturated blue for active states, indicating user interaction.
-   **Background**: `#ffffff` — The default background for most content areas, providing a clean canvas.
-   **Background Subtle**: `#f8fafd` — A very light, almost white, background used for subtle sectioning or secondary content blocks.
-   **Background Accent**: `#e5edf5` — A light blue-grey, used for secondary buttons, subtle borders, or background tints.
-   **Text Primary**: `#000000` — The main text color for headings and body copy on light backgrounds, ensuring high contrast.
-   **Text Heading**: `#061b31` — A very dark blue-grey, often used for prominent headings and important textual information.
-   **Text Secondary**: `#50617a` — A medium blue-grey for secondary text, descriptions, and less emphasized content.
-   **Text Muted**: `#64748d` — A lighter blue-grey for tertiary text, captions, and subtle hints.
-   **Text Input Label**: `#273951` — A specific dark blue-grey used for form input labels.
-   **Text Placeholder**: `#7d8ba4` — A light blue-grey for placeholder text within form inputs.
-   **Text Inverse**: `#ffffff` — White text, used primarily on dark or primary-colored backgrounds.
-   **Border**: `#e5edf5` (inferred from screenshot) — A light blue-grey for general component borders and dividers.
-   **Border Subtle**: `#a8c3de4d` — A very light, translucent blue-grey for subtle borders or separators.
-   **Accent Orange**: `#ff6118` — A vibrant orange, used as a gradient stop and for occasional highlight elements.
-   **Accent Peach**: `#ffe0d1` — A soft peach, used as a gradient stop or for subtle background accents.
-   **Accent Lavender**: `#e2e4ff` — A light lavender, used as a gradient stop or for subtle background accents.
-   **Accent Success**: `#00d66f` — A bright green, used for success indicators or positive feedback.
-   **Dark Background**: `#000000` — Pure black, used as a background in dark mode contexts.
-   **Dark Surface**: `#0d1738` — A very dark blue-grey, used for card backgrounds or distinct sections in dark mode.
-   **Dark Surface Hover**: `#1a3a5c` — A slightly lighter dark blue-grey for hover states on dark surfaces.
-   **Dark Text**: `#ffffff` — White text, ensuring readability on dark backgrounds.
-   **Dark Text Muted**: `#7d8ba4` — A muted blue-grey for secondary text on dark backgrounds.

## 3. Typography Rules
-   **Font Family**: `sohne-var, ui-sans-serif, system-ui, sans-serif`
-   **Hierarchy**:
    -   **Display**: `sohne-var` `40px` `700` · line-height `1.2` · tracking `none` · Used for prominent hero headlines.
    -   **Heading Large**: `sohne-var` `32px` `700` · line-height `1.2` · tracking `none` · For main section titles.
    -   **Heading Medium**: `sohne-var` `26px` `700` · line-height `1.2` · tracking `none` · For sub-section titles.
    -   **Heading Small**: `sohne-var` `22px` `400` · line-height `1.5` · tracking `none` · For card titles or feature headings.
    -   **Body**: `sohne-var` `16px` `400` · line-height `1.5` · tracking `none` · Standard paragraph text for readability.
    -   **Caption**: `sohne-var` `14px` `400` · line-height `1.3` · tracking `none` · For secondary information, labels, and metadata.
    -   **Small**: `sohne-var` `10px` `400` · line-height `1.2` · tracking `none` · For very fine print or specific data points.
    -   **Code/Mono**: `SFMono-Regular` `14px` `400` · line-height `1.4` · tracking `none` · (inferred) For code snippets or technical values.
-   **Principles**
    *   **Consistency**: The `sohne-var` typeface is used universally, establishing a strong and consistent brand voice.
    *   **Hierarchy through Weight & Size**: Visual hierarchy is primarily established by varying font size and weight, with `700` for headings and `400` for body text.
    *   **Generous Line Height**: Body text maintains a `1.5` line height for optimal readability, especially in longer passages.
    *   **Minimal Tracking**: Text uses default or slightly tighter tracking to maintain a clean and professional appearance.
    *   **Clarity in Data**: Smaller font sizes like `10px` are reserved for numerical data or secondary metrics, often paired with `tabular-nums--tight` (from extracted classes) for alignment.

## 4. Component Stylings

### Buttons

#### Primary Button
A prominent, solid blue button with white text, used for primary calls-to-action. On hover, the background subtly darkens, and the button maintains a slight lift.
```css
.button-primary {
  background-color: var(--color-primary, #533afd);
  color: var(--color-text-inverse, #ffffff);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  font-size: 16px;
  font-weight: 400;
  padding: 16px 24px;
  border: none;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  transition: background-color var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1)), transform var(--motion-duration-fast, 0.1s) ease-out, box-shadow var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1));
}

.button-primary:hover {
  background-color: var(--color-primary-hover, #665efd); /* inferred from input hover border */
  transform: translateY(-1px); /* inferred from screenshot */
  box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.1); /* inferred from screenshot */
}

.button-primary:active {
  background-color: var(--color-primary-active, #4236cc); /* inferred from screenshot */
  transform: translateY(0);
  box-shadow: none;
}

.button-primary:disabled {
  background-color: var(--color-background-accent, #e5edf5);
  color: var(--color-text-muted, #64748d);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
```


<details>
<summary>Secondary Button</summary>

A light blue-grey button with dark text, used for secondary actions or less emphasized calls-to-action. On hover, the background darkens slightly.
```css
.button-secondary {
  background-color: var(--color-background-accent, #e5edf5);
  color: var(--color-text-heading, #061b31);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 400;
  padding: 12px 20px;
  border: none;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  transition: background-color var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1));
}

.button-secondary:hover {
  background-color: #d1e0ed; /* inferred from screenshot */
}

.button-secondary:active {
  background-color: #c0d3e0; /* inferred from screenshot */
}

.button-secondary:disabled {
  background-color: var(--color-background-accent, #e5edf5);
  color: var(--color-text-muted, #64748d);
  cursor: not-allowed;
}
```

</details>

<details>
<summary>Ghost Button</summary>

A transparent button with primary blue text, often used for subtle actions or navigation within a content block. On hover, the text color deepens slightly, and a subtle underline appears.
```css
.button-ghost {
  background-color: transparent;
  color: var(--color-primary, #533afd);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 400;
  padding: 12px 20px;
  border: none;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  transition: color var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1)), text-decoration var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1));
}

.button-ghost:hover {
  color: var(--color-primary-hover, #665efd);
  text-decoration: underline; /* inferred from screenshot */
}

.button-ghost:active {
  color: var(--color-primary-active, #4236cc);
  text-decoration: underline;
}

.button-ghost:disabled {
  color: var(--color-text-muted, #64748d);
  cursor: not-allowed;
  text-decoration: none;
}
```

</details>
### Cards & Containers

#### Standard Card
A white rectangular container with subtly rounded corners and a soft shadow, used to group related content. On hover, the shadow subtly expands, giving a sense of lift.
```css
.card {
  background-color: var(--color-background, #ffffff);
  color: var(--color-text-primary, #000000);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  padding: var(--spacing-xxl, 24px); /* inferred from screenshot */
  border: 1px solid var(--color-border, #e5edf5); /* inferred from screenshot */
  border-radius: var(--radius-md, 6px);
  box-shadow: var(--elevation-card, 0px 3px 6px rgba(23, 23, 23, 0.06));
  transition: box-shadow var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1));
}

.card:hover {
  box-shadow: var(--elevation-hover, 0px 15px 35px rgba(23, 23, 23, 0.08));
}
```

### Inputs & Forms

#### Text Input
A standard text input field with a light border and rounded corners. On focus, a subtle blue shadow appears, and the border color changes to the primary blue. Disabled inputs have a muted background and border.
```css
.input-text {
  background-color: var(--color-background, #ffffff);
  color: var(--color-text-heading, #061b31);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  font-size: 16px;
  font-weight: 400;
  padding: 12px 16px;
  border: 1px solid var(--color-border, #e5edf5);
  border-radius: var(--radius-sm, 4px);
  transition: border-color var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1)), box-shadow var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1));
}

.input-text::placeholder {
  color: var(--color-text-placeholder, #7d8ba4);
}

.input-text:focus {
  outline: none;
  border-color: var(--color-primary, #533afd);
  box-shadow: 0 0 0 3px rgba(99, 91, 255, 0.1); /* from extracted pseudoStates focus */
}

.input-text:disabled {
  background-color: var(--color-background-subtle, #f8fafd);
  border-color: var(--color-border-subtle, #a8c3de4d);
  color: var(--color-text-muted, #64748d);
  cursor: not-allowed;
}
```


<details>
<summary>Form Label</summary>

A dark text label for form fields, typically positioned above the input.
```css
.form-label {
  color: var(--color-text-input-label, #273951);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 400;
  margin-bottom: var(--spacing-xs, 4px); /* inferred from screenshot */
  display: block;
  transition: color var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1));
}
```

</details>

<details>
<summary>Checkbox/Radio</summary>

A custom checkbox or radio input with a distinct visual state for checked.
```css
.checkbox, .radio {
  appearance: none;
  width: 18px; /* inferred from screenshot */
  height: 18px; /* inferred from screenshot */
  border: 1px solid var(--color-border, #e5edf5);
  border-radius: var(--radius-xs, 3px); /* Checkbox */
  border-radius: var(--radius-full, 100px); /* Radio */
  background-color: var(--color-background, #ffffff);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--motion-duration-fast, 0.1s) ease-out, border-color var(--motion-duration-fast, 0.1s) ease-out;
}

.checkbox:checked, .radio:checked {
  background-color: var(--color-primary, #533afd);
  border-color: var(--color-primary, #533afd);
}

.checkbox:checked::before {
  content: '✓'; /* inferred from screenshot */
  color: var(--color-text-inverse, #ffffff);
  font-size: 12px; /* inferred from screenshot */
  line-height: 1;
}

.radio:checked::before {
  content: '';
  width: 8px; /* inferred from screenshot */
  height: 8px; /* inferred from screenshot */
  border-radius: var(--radius-full, 100px);
  background-color: var(--color-text-inverse, #ffffff);
}

.checkbox:focus, .radio:focus {
  outline: 2px solid var(--color-primary, #533afd); /* inferred from screenshot */
  outline-offset: 2px; /* inferred from screenshot */
}

.checkbox:disabled, .radio:disabled {
  background-color: var(--color-background-subtle, #f8fafd);
  border-color: var(--color-border-subtle, #a8c3de4d);
  cursor: not-allowed;
}
```

</details>
### Navigation

#### Top Navigation Bar
A fixed navigation bar at the top of the viewport, featuring the Stripe logo, navigation links, and action buttons. It maintains a white background with a subtle shadow.
```css
.top-nav-bar {
  background-color: var(--color-background, #ffffff);
  padding: var(--spacing-lg, 16px) var(--spacing-xxl, 24px); /* inferred from screenshot */
  border-bottom: 1px solid var(--color-border, #e5edf5); /* inferred from screenshot */
  box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.04); /* inferred from screenshot */
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  width: 100%;
  z-index: var(--elevation-z-navigation, 2);
  transition: box-shadow var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1));
}
```


<details>
<summary>Navigation Link</summary>

Individual links within the top navigation, typically dark text. On hover, they show a subtle arrow animation and a color change.
```css
.nav-link {
  color: var(--color-text-heading, #061b31);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 400;
  text-decoration: none;
  padding: var(--spacing-sm, 8px) var(--spacing-md, 12px); /* inferred from screenshot */
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs, 4px);
  transition: color var(--motion-duration-medium, 0.3s) var(--motion-easing-standard, cubic-bezier(0.33, 1, 0.68, 1));
}

.nav-link:hover {
  color: var(--color-primary, #533afd); /* inferred from screenshot */
}

.nav-link.active,
.nav-link[aria-current="page"] {
  color: var(--color-primary, #533afd);
  font-weight: 500; /* inferred from screenshot */
  border-bottom: 2px solid var(--color-primary, #533afd); /* inferred from screenshot */
}
```

</details>

<details>
<summary>Dropdown Menu</summary>

A menu that appears below a navigation link on hover, typically with a white background and shadow.
```css
.dropdown-menu {
  background-color: var(--color-background, #ffffff);
  border-radius: var(--radius-md, 6px);
  box-shadow: var(--elevation-modal, 0px 16px 32px rgba(50, 50, 93, 0.12));
  padding: var(--spacing-lg, 16px);
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 200px; /* inferred from screenshot */
  z-index: var(--elevation-z-dialog, 3);
  opacity: 0;
  visibility: hidden;
  transform: translateY(10px); /* inferred from screenshot */
  transition: opacity var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1)), transform var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1)), visibility var(--motion-duration-base, 0.2s) step-end;
}

.nav-link-parent:hover .dropdown-menu {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
  transition: opacity var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1)), transform var(--motion-duration-base, 0.2s) var(--motion-easing-ease-out, cubic-bezier(0.25, 1, 0.5, 1)), visibility var(--motion-duration-base, 0.2s) step-start;
}

.dropdown-menu-item {
  color: var(--color-text-heading, #061b31);
  font-family: var(--typography-family-primary, sohne-var, ui-sans-serif, system-ui, sans-serif);
  font-size: 16px;
  font-weight: 400;
  padding: var(--spacing-sm, 8px) var(--spacing-md, 12px);
  text-decoration: none;
  display: block;
  transition: background-color var(--motion-duration-fast, 0.1s) ease-out, color var(--motion-duration-fast, 0.1s) ease-out;
}

.dropdown-menu-item:hover {
  background-color: var(--color-background-subtle, #f8fafd);
  color: var(--color-primary, #533afd);
}
```

</details>
### Links

#### Standard Link
A default inline text link, typically primary blue. On hover, it darkens and gains an underline.
```css
.link-standard {
  color: var(--color-primary, #533afd);
  text-decoration: none;
  transition: color var(--motion-duration-fast, 0.1s) ease-out, text-decoration var(--motion-duration-fast, 0.1s) ease-out;
}

.link-standard:hover {
  color: var(--color-primary-hover, #665efd);
  text-decoration: underline;
}

.link-standard:visited {
  color: var(--color-primary, #533afd); /* inferred, often same as primary */
}
```


<details>
<summary>Secondary Link</summary>

A text link used for less prominent actions, often in muted blue-grey. On hover, it darkens and gains an underline.
```css
.link-secondary {
  color: var(--color-text-secondary, #50617a);
  text-decoration: none;
  transition: color var(--motion-duration-fast, 0.1s) ease-out, text-decoration var(--motion-duration-fast, 0.1s) ease-out;
}

.link-secondary:hover {
  color: var(--color-text-heading, #061b31); /* inferred from screenshot */
  text-decoration: underline;
}

.link-secondary:visited {
  color: var(--color-text-secondary, #50617a); /* inferred, often same as secondary */
}
```

</details>
### Badges
(none observed in source)

## 5. Layout Principles
-   **Spacing System**: Stripe utilizes a `4px` base unit for its spacing system, creating a harmonious and predictable rhythm across the interface.
    -   Base `4px` → `0, 4, 8, 12, 16, 20, 24, 32`
    -   `0px`: No spacing, for tightly grouped elements.
    -   `4px` (`xxs`): Smallest separation for inline elements or icons.
    -   `8px` (`xs`): Standard spacing for small components or text lines.
    -   `12px` (`sm`): Padding within smaller buttons or input fields.
    -   `16px` (`md`): Standard component padding, vertical spacing between text blocks.
    -   `20px` (`lg`): Padding for larger interactive elements or minor section breaks.
    -   `24px` (`xl`): Major vertical spacing between sections, card padding.
    -   `32px` (`xxl`): Significant separation between main content blocks or large hero elements.
-   **Grid & Container**:
    _Note: container widths and column counts are extracted from the source breakpoints. The values below are based on these measurements._
    Stripe's layout is flexible, adapting to various screen sizes. The main content is typically constrained within a maximum width to ensure readability and visual balance.
    -   **Max Width**: `1280px` (from `min-width: 1280px` breakpoint)
    -   **Columns**: `12` columns (inferred from common web design practice)
    -   **Gutter**: `24px` (inferred from screenshot)
    -   **Section Padding**: `64px` vertical, `32px` horizontal (inferred from screenshot)
-   **Whitespace Philosophy**: Stripe employs abundant whitespace to create a sense of openness, reduce cognitive load, and highlight key content. Generous padding around components and between sections ensures that elements breathe, drawing attention to important calls-to-action and information. This deliberate use of negative space contributes to the brand's premium and sophisticated feel, preventing visual clutter even with complex data displays.
-   **Border Radius Scale**:
    -   `3px` (`xs`): For very subtle rounding, e.g., small badges.
    -   `4px` (`sm`): Standard for buttons, input fields, and small interactive elements.
    -   `6px` (`md`): Used for cards and larger containers.
    -   `8px` (`lg`): For more pronounced rounding on larger UI elements or modals.
    -   `100px` (`full`): For pill-shaped elements like radio buttons or very rounded buttons.

## 6. Depth & Elevation
Stripe uses a subtle elevation system to indicate hierarchy and interactivity, primarily through soft shadows and distinct z-index values.

-   **Flat (z-0)**: `none` — Default state for most background elements and static content.
-   **Base (z-1)**: `none` — Used for foundational interactive elements like navigation containers.
-   **Navigation (z-2)**: `0px 1px 2px rgba(0,0,0,0.04)` (inferred) — For the sticky top navigation bar when scrolled.
-   **Card (z-3)**: `0px 3px 6px rgba(23, 23, 23, 0.06)` — Standard shadow for cards and elevated content blocks.
-   **Card Hover (z-3)**: `0px 15px 35px rgba(23, 23, 23, 0.08)` — Enhanced shadow on card hover for interactive feedback.
-   **Dialog (z-4)**: `0px 16px 32px rgba(50, 50, 93, 0.12)` — For modal dialogs, dropdowns, and temporary overlays, ensuring they stand out.
-   **Chat Widget (z-99)**: `0px 16px 32px rgba(50, 50, 93, 0.12)` (inferred) — For persistent chat widgets.
-   **Notification (z-9999)**: `0px 16px 32px rgba(50, 50, 93, 0.12)` (inferred) — For high-priority notifications.
-   **Iframe (z-2147483639)**: `none` (inferred) — For embedded content with very high stacking context.

**Shadow Philosophy**: Stripe's shadow philosophy is restrained, focusing on subtle depth cues rather than heavy visual effects. Shadows are primarily used to differentiate interactive elements like cards and buttons, and to provide a clear sense of hierarchy for transient UI elements such as dropdowns and modals. The shadows are soft, diffuse, and typically dark grey, maintaining the brand's clean and modern aesthetic without appearing heavy or distracting.

## 7. Do's and Don'ts

### Do's
*   **Do** use `#533afd` for all primary interactive elements like the Primary Button and standard links.
*   **Do** ensure body text uses `#000000` on `#ffffff` backgrounds for a contrast ratio of 17.37, passing AAA.
*   **Do** apply `sohne-var` `700` `32px` for main section headings (`Heading Large`).
*   **Do** maintain `24px` vertical spacing between distinct content blocks or cards.
*   **Do** use `4px` border-radius for all interactive elements like Buttons and Text Inputs.
*   **Do** provide a `3px` blue focus ring (`rgba(99, 91, 255, 0.1) 0px 0px 0px 3px`) for Text Inputs.
*   **Do** use `#061b31` for prominent text on `#ffe6f5` backgrounds, achieving a 14.8 contrast ratio (AAA).
*   **Do** utilize the `0px 15px 35px rgba(23, 23, 23, 0.08)` shadow for card hover states.
*   **Do** ensure navigation links (`.nav-link`) animate color over `0.3s` with `cubic-bezier(0.33, 1, 0.68, 1)`.

### Don'ts
*   **Don't** use `#50617a` text on `#f8fafd` backgrounds, as its 6.03 contrast ratio barely passes AA, consider a darker shade.
*   **Don't** introduce custom spacing values; adhere strictly to the `4, 8, 12, 16, 20, 24, 32px` scale.
*   **Don't** use `sohne-var` `300` weight for body text; reserve `400` for standard readability.
*   **Don't** apply shadows with high opacity or large spreads; maintain the subtle `0px 3px 6px rgba(23, 23, 23, 0.06)` card default.
*   **Don't** use border-radius values other than `3, 4, 6, 8, 100px` for components.
*   **Don't** omit the underline on hover for `link-standard` and `link-secondary` components.
*   **Don't** use `#64748d` for critical information; it's reserved for `text-muted` roles.
*   **Don't** use `background-accent: #e5edf5` as a primary button background; save it for secondary actions.

## 8. Responsive Behavior
_Note: breakpoints below are derived from measured media queries in the source. Adjust to the brand's actual media queries when implementing._

-   **Measured Breakpoints**:
    -   **Mobile Small** (~320px): Content stacks vertically, font sizes may scale down.
    -   **Mobile Large** (~639px): Navigation collapses into a hamburger menu, cards stack.
    -   **Tablet** (~640px): Two-column layouts may emerge, larger typography.
    -   **Desktop** (~940px): Full navigation visible, multi-column grids common.
    -   **Desktop Large** (~1280px): Max content width engaged, ample whitespace.
-   **Touch Targets**:
    -   Interactive elements like buttons and links should have a minimum touch target size of `44px` (inferred).
    -   Maintain at least `8px` of clear space around touch targets to prevent accidental taps.
-   **Collapsing Strategy**:
    -   **Navigation**: Top navigation links collapse into a hamburger menu on screens below `640px`.
    -   **Cards**: Multi-column card layouts stack vertically on mobile breakpoints.
    -   **Typography**: Display and Heading Large font sizes scale down by `20-30%` on mobile.
    -   **Padding**: Horizontal section padding reduces from `32px` to `16px` on mobile.
    -   **Forms**: Multi-column form layouts collapse to single columns on smaller screens.
    -   **Spacing**: Vertical spacing between major sections may be reduced by `25%` on mobile.

## 9. Agent Prompt Guide

-   **Quick Color Reference**:
    -   primary: `#533afd`
    -   primary-hover: `#665efd`
    -   background: `#ffffff`
    -   background-subtle: `#f8fafd`
    -   text-primary: `#000000`
    -   text-heading: `#061b31`
    -   text-secondary: `#50617a`
    -   text-muted: `#64748d`
    -   text-inverse: `#ffffff`
    -   border: `#e5edf5`
    -   accent-orange: `#ff6118`
    -   dark-background: `#000000`
    -   dark-surface: `#0d1738`
    -   dark-text: `#ffffff`

-   **Iteration Guide**:
    1.  Always use `sohne-var` as the primary font family.
    2.  Ensure CTAs use `Primary Button` styling with `#533afd` background and `16px 24px` padding.
    3.  Set body text to `16px` `400` weight with `1.5` line-height.
    4.  Apply spacing from the `4, 8, 12, 16, 20, 24, 32px` scale.
    5.  Use `4px` border-radius for buttons and inputs, `6px` for cards.
    6.  All input fields must include a `3px` blue focus ring (`rgba(99, 91, 255, 0.1) 0px 0px 0px 3px`).
    7.  Cards should default to `0px 3px 6px rgba(23, 23, 23, 0.06)` shadow, escalating to `0px 15px 35px rgba(23, 23, 23, 0.08)` on hover.
    8.  Navigation links (`.nav-link`) must change color to `#533afd` on hover with a `0.3s` transition.
    9.  Ensure main body text `#000000` on `#ffffff` backgrounds passes AAA contrast (17.37 ratio).
    10. Implement mobile-first design, collapsing navigation below `640px` viewport width.
    11. Use `cubic-bezier(0.33, 1, 0.68, 1)` for standard easing durations like `0.2s` or `0.3s`.
    12. Apply the dynamic orange-pink-purple gradient (`#ff6118` to `#ea2261` to `#533afd` inferred) as a signature background element.

<!-- DESIGNMD_VALIDATOR_WARNINGS
{
  "version": 1,
  "generatedAt": "2026-09-22T16:43:55.701Z",
  "summary": {
    "unpairedBanned": 9,
    "bannedPhrase": 0,
    "total": 9
  },
  "warnings": [
    {
      "kind": "unpaired-banned-word",
      "term": "clean",
      "sentence": "Stripe's design system exudes a sophisticated yet approachable aesthetic, characterized by a clean layout and strategic use of vibrant gradients."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "sophisticated",
      "sentence": "Stripe's design system exudes a sophisticated yet approachable aesthetic, characterized by a clean layout and strategic use of vibrant gradients."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "approachable",
      "sentence": "Stripe's design system exudes a sophisticated yet approachable aesthetic, characterized by a clean layout and strategic use of vibrant gradients."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "polished",
      "sentence": "Subtle CSS animations enhance interactivity, particularly on navigation elements and card hovers, contributing to a polished user experience."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "balanced",
      "sentence": "The atmosphere is one of technological precision and forward-thinking innovation, achieved through a balanced interplay of crisp typography, ample whitespace, and carefully chosen accent colors."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "forward-thinking",
      "sentence": "The atmosphere is one of technological precision and forward-thinking innovation, achieved through a balanced interplay of crisp typography, ample whitespace, and carefully chosen accent colors."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "cohesive",
      "sentence": "Illustrations are abstract and geometric, often incorporating the brand's gradient palette, reinforcing a cohesive digital identity."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "professional",
      "sentence": "The overall impression is professional and trustworthy, guiding users through complex financial services with clarity and visual appeal."
    },
    {
      "kind": "unpaired-banned-word",
      "term": "trustworthy",
      "sentence": "The overall impression is professional and trustworthy, guiding users through complex financial services with clarity and visual appeal."
    }
  ]
}
-->
done (33.4 KB)
