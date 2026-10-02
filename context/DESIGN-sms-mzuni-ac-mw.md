---
name: Mzuzu University IMIS
url: https://sms.mzuni.ac.mw/home
colors:
  primary: '#15803d'
  primary-hover: '#126f35' # Inferred darker shade for hover
  background: '#f3f4f6'
  background-alt: '#f9fafb'
  surface: '#ffffff'
  text-primary: '#000000'
  text-secondary: '#6b7280'
  text-muted: '#9ca3af'
  text-inverse: '#ffffff'
  border: '#e5e7eb'
  border-light: '#d1d5db'
  input-focus-border: '#3b82f6'
  link-color: '#15803d' # Explicitly named for links
  link-hover: '#126f35' # Inferred darker shade for link hover
  dark-background: '#0a0e13'
  dark-surface: '#111827'
  dark-text: '#ffffff'
  dark-text-muted: '#6b7280'
  dark-border: '#374151'
typography:
  display:
    family: 'poppins'
    size: 24px
    weight: 500
    line-height: 1.2
  body:
    family: 'poppins'
    size: 16px
    weight: 400
    line-height: 1.5
  small:
    family: 'poppins'
    size: 14px
    weight: 400
    line-height: 1.5
  caption:
    family: 'poppins'
    size: 12px
    weight: 400
    line-height: 1.5
spacing:
  base: 4px
  scale: [8, 12, 16, 20, 24, 32, 40]
radius:
  sm: 6px
  md: 16px
elevation:
  card: '0px 1px 2px rgba(0,0,0,0.05)'
components:
  button-primary:
    bg: '{colors.primary}'
    text: '{colors.text-inverse}'
    radius: '{radius.sm}'
    padding: '10px 32px'
  card:
    bg: '{colors.surface}'
    radius: '{radius.md}'
    shadow: '{elevation.card}'
  input:
    bg: '{colors.surface}'
    text: '{colors.text-primary}'
    border: '{colors.border-light}'
    radius: '{radius.sm}'
    padding: '10px 12px'
motion:
  duration-base: '150ms'
  easing-standard: 'ease-in-out'
layout:
  breakpoints:
    sm: 640px
    md: 768px
    lg: 1024px
    xl: 1280px
    xxl: 1536px
---

# Design System Inspired by Mzuzu University IMIS

## 1. Visual Theme & Atmosphere
The Mzuzu University IMIS login page presents a clean and focused interface, centered around a single card component. The primary color, a vibrant `#15803d` green, is used for the main call-to-action button and interactive elements, providing a clear focal point. Typography is consistently set in the 'Poppins' font, contributing to a modern and legible aesthetic, with `24px` for the main heading and `16px` for body text.

The overall atmosphere is one of simplicity and professionalism, achieved through ample whitespace, a light `#f3f4f6` background, and subtle `0px 1px 2px rgba(0,0,0,0.05)` shadows on the central card. The design prioritizes user clarity and ease of interaction, with clearly defined input fields and a prominent login button. No complex animations or gradients are detected, maintaining a straightforward visual experience.

Key Characteristics:
- Centered card layout on a light `#f3f4f6` background.
- Primary brand color is a distinct `#15803d` green.
- Typography uses 'Poppins' for all text elements.
- Soft `0px 1px 2px rgba(0,0,0,0.05)` shadow on the main card.
- Rounded corners applied with `6px` and `16px` radii.
- No animation detected beyond standard CSS transitions.

## 2. Color Palette & Roles
The color palette is concise, focusing on a strong primary green and a well-defined neutral scale to support content and structure.

-   **Primary**
    -   `primary`: `#15803d` – The main brand color, used for primary buttons, active states, and important links.
    -   `primary-hover`: `#126f35` (inferred from screenshot) – A slightly darker shade of the primary green, used for hover states on interactive elements.

-   **Interactive**
    -   `input-focus-border`: `#3b82f6` – A clear blue used for the focus ring around input fields, indicating user interaction.
    -   `link-color`: `#15803d` – Default color for text links.
    -   `link-hover`: `#126f35` (inferred from screenshot) – The color for text links on hover, providing visual feedback.

-   **Neutral Scale**
    -   `text-primary`: `#000000` – Used for main headings and primary body text, ensuring high readability.
    -   `text-secondary`: `#6b7280` – For labels, secondary information, and less prominent text.
    -   `text-muted`: `#9ca3af` – Used for placeholder text in input fields and subtle copyright information.
    -   `text-inverse`: `#ffffff` – Text color used on primary colored backgrounds, such as the login button.
    -   `background`: `#f3f4f6` – The overall page background color, providing a light, airy canvas.
    -   `background-alt`: `#f9fafb` – A slightly lighter background, potentially used for alternating table rows or subtle section distinctions.
    -   `surface`: `#ffffff` – The background color for cards, modals, and main content areas.

-   **Surface & Borders**
    -   `border`: `#e5e7eb` – A light gray used for subtle borders, such as around cards.
    -   `border-light`: `#d1d5db` – A slightly lighter gray, specifically used for input field borders.

-   **Dark Mode (Inferred from CSS variables)**
    -   `dark-background`: `#0a0e13` – The background color for the page in dark mode.
    -   `dark-surface`: `#111827` – The background color for cards and containers in dark mode.
    -   `dark-text`: `#ffffff` – Primary text color in dark mode.
    -   `dark-text-muted`: `#6b7280` – Muted or secondary text color in dark mode.
    -   `dark-border`: `#374151` – Border color for elements in dark mode.

## 3. Typography Rules
The typography system relies solely on the 'Poppins' typeface, ensuring a consistent and modern aesthetic across all text elements.

-   **Font Family**:
    -   Primary: `'poppins', ui-sans-serif, system-ui, sans-serif`
    -   Monospace: `'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', monospace` (inferred fallback)

-   **Hierarchy**:
    -   **Display/H1**: `'poppins'` `24px` `500` · line-height `1.2` · tracking `none` · Used for prominent page titles like "Sign in to your account".
    -   **Body**: `'poppins'` `16px` `400` · line-height `1.5` · tracking `none` · Standard text for paragraphs and general content.
    -   **Small**: `'poppins'` `14px` `400` · line-height `1.5` · tracking `none` · Used for input labels, secondary information, and form elements.
    -   **Caption**: `'poppins'` `12px` `400` · line-height `1.5` · tracking `none` · For legal text, copyright notices, or very fine print.

-   **Principles**:
    -   Maintain a clear visual hierarchy by varying font size and weight, with `24px` for primary headings and `16px` for body content.
    -   Prioritize readability with a generous `1.5` line-height for body text, ensuring comfortable reading.
    -   Utilize the 'Poppins' font consistently across all text elements to establish a cohesive brand voice.
    -   Employ `400` weight for most text to ensure legibility, reserving `500` for key titles.

## 4. Component Stylings

### Buttons
Buttons feature a consistent `6px` border-radius and `150ms ease-in-out` transitions for smooth feedback.

#### Primary Button
A prominent green button for primary actions, with white text. On interaction, it provides subtle visual feedback.

```css
.button-primary {
  background-color: var(--color-primary, #15803d);
  color: var(--color-text-inverse, #ffffff);
  font-family: var(--typography-small-family, 'poppins', ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 500;
  padding: 10px 32px;
  border: none;
  border-radius: var(--radius-sm, 6px);
  cursor: pointer;
  transition: background-color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out),
              transform var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out);
}

.button-primary:hover {
  background-color: var(--color-primary-hover, #126f35); /* inferred from screenshot */
}

.button-primary:active {
  transform: scale(0.95); /* extracted from pseudoStates.active */
}

.button-primary:disabled {
  cursor: default; /* extracted from pseudoStates.disabled */
  opacity: 0.6; /* inferred from screenshot */
  background-color: var(--color-border-light, #d1d5db); /* inferred from screenshot */
  color: var(--color-text-secondary, #6b7280); /* inferred from screenshot */
}
```


<details>
<summary>Secondary Button</summary>

(None observed in source, inferred as a common variant)
A button for secondary actions, typically with a transparent background and a border.

```css
.button-secondary {
  background-color: transparent;
  color: var(--color-primary, #15803d);
  font-family: var(--typography-small-family, 'poppins', ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 500;
  padding: 10px 32px;
  border: 1px solid var(--color-primary, #15803d); /* inferred from screenshot */
  border-radius: var(--radius-sm, 6px);
  cursor: pointer;
  transition: background-color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out),
              color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out),
              border-color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out);
}

.button-secondary:hover {
  background-color: var(--color-primary, #15803d); /* inferred from screenshot */
  color: var(--color-text-inverse, #ffffff); /* inferred from screenshot */
}

.button-secondary:active {
  transform: scale(0.95); /* inferred from pseudoStates.active */
}

.button-secondary:disabled {
  cursor: default; /* inferred from pseudoStates.disabled */
  opacity: 0.6; /* inferred from screenshot */
  border-color: var(--color-border-light, #d1d5db); /* inferred from screenshot */
  color: var(--color-text-secondary, #6b7280); /* inferred from screenshot */
}
```

</details>

<details>
<summary>Ghost Button</summary>

(None observed in source, inferred as a common variant)
A text-only button for tertiary actions, often used for navigation or less emphasized interactions.

```css
.button-ghost {
  background-color: transparent;
  color: var(--color-primary, #15803d);
  font-family: var(--typography-small-family, 'poppins', ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 500;
  padding: 10px 16px; /* inferred from screenshot */
  border: none;
  border-radius: var(--radius-sm, 6px);
  cursor: pointer;
  transition: background-color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out),
              color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out);
}

.button-ghost:hover {
  background-color: var(--color-background-alt, #f9fafb); /* inferred from screenshot */
  color: var(--color-primary-hover, #126f35); /* inferred from screenshot */
}

.button-ghost:active {
  transform: scale(0.95); /* inferred from pseudoStates.active */
}

.button-ghost:disabled {
  cursor: default; /* inferred from pseudoStates.disabled */
  opacity: 0.6; /* inferred from screenshot */
  color: var(--color-text-muted, #9ca3af); /* inferred from screenshot */
}
```

</details>
### Cards & Containers

#### Standard Card
A central container for content, featuring a subtle shadow and rounded corners for a soft, approachable feel. The card uses a backdrop blur effect.

```css
.card {
  background-color: var(--color-surface, #ffffff);
  color: var(--color-text-primary, #000000);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: var(--radius-md, 16px);
  box-shadow: var(--elevation-card, 0px 1px 2px rgba(0,0,0,0.05));
  backdrop-filter: blur(12px); /* inferred from componentFamilies.topClassStrings 'backdrop-blur-xl' */
  padding: 40px; /* inferred from componentFamilies.topClassStrings 'px-10 py-8' */
  transition: box-shadow var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out),
              border-color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out);
}

.card:hover {
  box-shadow: 0px 2px 8px rgba(0,0,0,0.08); /* inferred from screenshot, slightly stronger shadow */
  border-color: var(--color-border-light, #d1d5db); /* inferred from screenshot */
}
```

### Inputs & Forms

#### Text Input
Standard text input field with a light border and rounded corners. Focus state is clearly indicated by a blue border and ring.

```css
.text-input {
  background-color: var(--color-surface, #ffffff);
  color: var(--color-text-primary, #1f2937);
  font-family: var(--typography-small-family, 'poppins', ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 400;
  padding: 10px 12px; /* inferred from componentFamilies.topClassStrings 'px-3 pt-5 pb-2' for label interaction */
  border: 1px solid var(--color-border-light, #d1d5db);
  border-radius: var(--radius-sm, 6px);
  width: 100%;
  transition: border-color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out),
              box-shadow var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out);
}

.text-input::placeholder {
  color: var(--color-text-muted, #9ca3af);
}

.text-input:focus {
  outline: 2px solid transparent; /* extracted from pseudoStates.focus */
  outline-offset: 2px; /* extracted from pseudoStates.focus */
  border-color: var(--color-input-focus-border, #3b82f6); /* extracted from cssVariables.scoped */
  box-shadow: var(--tw-ring-offset-shadow, 0 0 #0000), var(--tw-ring-shadow, 0 0 #0000), var(--tw-shadow, 0 0 #0000); /* extracted from pseudoStates.focus */
}

.text-input:disabled {
  cursor: default; /* extracted from pseudoStates.disabled */
  background-color: var(--color-background, #f3f4f6); /* inferred from screenshot */
  border-color: var(--color-border, #e5e7eb); /* inferred from screenshot */
  color: var(--color-text-muted, #9ca3af); /* inferred from screenshot */
}
```


<details>
<summary>Form Label</summary>

Labels for input fields, which animate on focus or when content is present.

```css
.form-label {
  position: absolute;
  left: 12px; /* inferred from componentFamilies.topClassStrings 'left-3' */
  top: 14px; /* inferred from componentFamilies.topClassStrings 'top-3.5' */
  font-family: var(--typography-small-family, 'poppins', ui-sans-serif, system-ui, sans-serif);
  font-size: 14px; /* inferred from componentFamilies.topClassStrings 'text-sm' */
  font-weight: 400;
  color: var(--color-text-secondary, #6b7280);
  transition: all var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out); /* extracted from componentFamilies.topClassStrings 'transition-all duration-150' */
  transform-origin: left top;
}

/* Specific peer-focus and peer-not-placeholder-shown styles are handled by JS/Tailwind classes */
/* For a pure CSS approach, these would require adjacent sibling selectors or parent-child state management */
/* .text-input:focus + .form-label,
.text-input:not(:placeholder-shown) + .form-label {
  top: 4px;
  font-size: 12px;
  color: var(--color-primary, #15803d);
} */
```

</details>
### Links

#### Standard Link
A standard text link, typically used for navigation or secondary actions like "Forgot password?".

```css
.link-standard {
  color: var(--color-link-color, #15803d);
  font-family: var(--typography-small-family, 'poppins', ui-sans-serif, system-ui, sans-serif);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: color var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out),
              text-decoration var(--motion-duration-base, 150ms) var(--motion-easing-standard, ease-in-out);
}

.link-standard:hover {
  color: var(--color-link-hover, #126f35); /* inferred from screenshot */
  text-decoration: underline; /* inferred from screenshot */
}

.link-standard:visited {
  color: var(--color-link-color, #15803d); /* inferred from screenshot */
}
```

## 5. Layout Principles
The layout emphasizes a clear, centered content area with generous spacing, creating a calm and focused user experience.

-   **Spacing System**:
    The spacing system is built on a `4px` base unit, providing a flexible yet consistent rhythm across the interface.
    -   Base: `4px`
    -   Scale: `[8px, 12px, 16px, 20px, 24px, 32px, 40px]` (derived from extracted `spacing` values)
    -   Usage Context:
        -   `8px`: Smallest internal spacing, e.g., between an icon and text.
        -   `12px`: Padding within input fields, spacing between small elements.
        -   `16px`: Standard spacing between form elements, internal component padding.
        -   `20px`: Moderate spacing for grouping related content.
        -   `24px`: Vertical spacing between sections or major components.
        -   `32px`: Horizontal padding for buttons, larger internal component spacing.
        -   `40px`: Generous padding within cards, significant vertical separation.

-   **Grid & Container** *(Suggested — not measured)*:
    _Note: container widths and column counts are not extracted from the source. The values below are reasonable defaults inferred from the visible layout density._
    -   Max Width: `384px` (inferred from `max-w-sm` class on the main content container)
    -   Columns: `12` (inferred from common practice)
    -   Gutter: `24px` (inferred for horizontal spacing between grid columns)
    -   Section Padding: `64px` vertical, `24px` horizontal (inferred for overall page content spacing)

-   **Whitespace Philosophy**:
    Whitespace is used generously to create a sense of calm and focus, particularly around the central card component. Elements are not crowded, allowing each piece of information or interactive element to breathe. This ample negative space enhances readability and reduces cognitive load, directing the user's attention to key actions.

-   **Border Radius Scale**:
    The design employs two primary border radii, contributing to a soft and friendly aesthetic.
    -   `sm`: `6px` – Applied to interactive elements like buttons and input fields for a subtle rounding.
    -   `md`: `16px` – Used for larger containers such as cards, providing a more pronounced rounded corner.

## 6. Depth & Elevation
The elevation system is minimal, focusing on a single, subtle shadow for cards to provide a sense of depth without distraction.

-   **Flat (z-0)**: `none` — Default for most background elements and text.
-   **Card (z-1)**: `0px 1px 2px rgba(0,0,0,0.05)` — Used for the main content card, providing a subtle lift from the background.

Shadow Philosophy:
The design adopts a subtle shadow philosophy, primarily using a single, low-intensity shadow for cards. This approach provides just enough visual separation to distinguish interactive or grouped content from the background without creating heavy or distracting visual layers. The focus is on a clean, light interface where depth is implied rather than overtly stated.

## 7. Do's and Don'ts

### Do's
-   **Do** use `#15803d` for all primary calls-to-action, such as the Login button, to maintain brand consistency.
-   **Do** ensure body text uses `#000000` on `#f3f4f6` backgrounds; this pair achieves a 19.08 contrast ratio, passing AAA.
-   **Do** apply `16px` border-radius to all Card components to maintain the soft, rounded aesthetic.
-   **Do** use the 'Poppins' font family for all text elements, maintaining a unified typographic voice.
-   **Do** provide at least `24px` of vertical spacing between major content blocks, like the card and copyright text.
-   **Do** use `14px` font size with `400` weight for all input labels and secondary information.
-   **Do** ensure button text, like `#ffffff` on `#15803d`, passes AA contrast with a 5.02 ratio.
-   **Do** use `6px` border-radius for all interactive elements, including buttons and text inputs.
-   **Do** use `#3b82f6` as the focus border color for text inputs to clearly indicate active fields.

### Don'ts
-   **Don't** use `#9ca3af` text on `#f9fafb` backgrounds; this pair has a 2.43 contrast ratio, failing AA accessibility.
-   **Don't** introduce any font families other than 'Poppins' for user-facing text.
-   **Don't** use padding values outside the defined `8px, 12px, 16px, 20px, 24px, 32px, 40px` spacing scale.
-   **Don't** apply shadows to elements other than the main Card component.
-   **Don't** use `16px` font size for captions or copyright text; reserve `12px` for such small text roles.
-   **Don't** use `#6b7280` text on backgrounds darker than `#ffffff` without re-checking contrast; on `#ffffff` it is 4.83 (AA).
-   **Don't** modify the `0px 1px 2px rgba(0,0,0,0.05)` shadow on the Card component.
-   **Don't** use a font weight greater than `500` for any text, as `500` is the heaviest observed.

## 8. Responsive Behavior
-   **Breakpoints**:
    -   **Mobile Small** (~320px): Stack all elements vertically; adjust padding to `16px` horizontal.
    -   **Mobile Large** (~640px): Card width expands to `90%` of viewport; typography scales slightly.
    -   **Tablet** (~768px): Card max-width remains `384px`; increase page padding to `32px` horizontal.
    -   **Desktop** (~1024px): Layout maintains centered card; ensure ample `64px` page padding.
    -   **Desktop Large** (~1280px): Content remains centered; no significant layout changes, increased whitespace.
    -   **XL Desktop** (~1536px): Maximize whitespace around the central content.

-   **Touch Targets**:
    -   Ensure all interactive elements, especially buttons, have a minimum touch target size of `44px` by `44px`.
    -   Maintain a minimum of `8px` clear spacing between touch targets to prevent accidental taps.

-   **Collapsing Strategy**:
    -   **Cards**: The main Card component should maintain its `384px` max-width and center alignment, scaling down to `90%` width on smaller viewports.
    -   **Typography**: Display `24px` text should scale down to `20px` on mobile screens for better fit.
    -   **Padding**: Horizontal page padding should reduce from `64px` to `16px` on mobile to optimize screen real estate.
    -   **Forms**: Input fields should always span `100%` width of their container, adapting to available space.
    -   **Spacing**: Vertical spacing between form elements can be slightly reduced on mobile, e.g., from `16px` to `12px`.

## 9. Agent Prompt Guide

-   **Quick Color Reference**:
    -   `primary`: `#15803d`
    -   `primary-hover`: `#126f35`
    -   `background`: `#f3f4f6`
    -   `background-alt`: `#f9fafb`
    -   `surface`: `#ffffff`
    -   `text-primary`: `#000000`
    -   `text-secondary`: `#6b7280`
    -   `text-muted`: `#9ca3af`
    -   `text-inverse`: `#ffffff`
    -   `border`: `#e5e7eb`
    -   `border-light`: `#d1d5db`
    -   `input-focus-border`: `#3b82f6`
    -   `link-color`: `#15803d`
    -   `link-hover`: `#126f35`
    -   `dark-background`: `#0a0e13`
    -   `dark-surface`: `#111827`
    -   `dark-text`: `#ffffff`
    -   `dark-text-muted`: `#6b7280`
    -   `dark-border`: `#374151`

-   **Iteration Guide**:
    1.  Always use `poppins` as the primary font family for all text elements.
    2.  Ensure primary calls-to-action (CTAs) are rendered as `button-primary` with a `#15803d` background and `#ffffff` text.
    3.  Set all button heights to at least `44px` for adequate touch targets.
    4.  Apply `6px` border-radius to all buttons and input fields.
    5.  Use `16px` border-radius for all Card components.
    6.  Maintain `24px` font size for the main display heading and `16px` for body text.
    7.  Utilize the `8px, 12px, 16px, 20px, 24px, 32px, 40px` spacing scale for all layout and component spacing.
    8.  Implement the `0px 1px 2px rgba(0,0,0,0.05)` shadow exclusively on Card components.
    9.  Ensure text inputs display a `#3b82f6` border on `:focus` state.
    10. On mobile (below `640px`), collapse the main content card to `90%` width with `16px` horizontal padding.
    11. Verify that `#000000` text on `#f3f4f6` background always passes AAA contrast.
    12. Implement `transform: scale(0.95)` on `:active` state for buttons, with a `150ms ease-in-out` transition.

<!-- DESIGNMD_VALIDATOR_WARNINGS
{
  "version": 1,
  "generatedAt": "2026-10-02T00:21:42.161Z",
  "summary": {
    "unpairedBanned": 1,
    "bannedPhrase": 0,
    "total": 1
  },
  "warnings": [
    {
      "kind": "unpaired-banned-word",
      "term": "clean",
      "sentence": "The Mzuzu University IMIS login page presents a clean and focused interface, centered around a single card component."
    }
  ]
}
-->
