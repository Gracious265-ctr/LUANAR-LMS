---
name: LUANAR SARIS Login
url: https://saris.luanar.ac.mw/systems/login/
colors:
  primary-gradient-start: '#764ba2'
  primary-gradient-end: '#667eea'
  background: '#e2e8f0'
  surface: '#ffffff'
  text-heading: '#111827'
  text-primary: '#000000'
  text-secondary: '#374151'
  text-muted: '#9ca3af'
  text-inverse: '#ffffff'
  border-subtle: '#e5e7eb'
  error-strong: '#dc2626'
  error-light: '#ef4444'
  link-hover: '#764ba2'
  focus-ring-shadow: 'rgba(102, 126, 234, 0.1)'
typography:
  display:
    family: 'Inter'
    size: 24px
    weight: 700
    line-height: 1.2
  body:
    family: 'Inter'
    size: 16px
    weight: 400
    line-height: 1.5
  small:
    family: 'Inter'
    size: 14px
    weight: 400
    line-height: 1.5
spacing:
  base: 4px
  scale: [8, 12, 16, 24, 32, 48]
radius:
  sm: 8px
  md: 12px
elevation:
  card: '0 25px 50px -12px rgba(0,0,0,0.25)'
  hover: '0 8px 25px rgba(102, 126, 234, 0.25)'
motion:
  duration-base: '0.3s'
  duration-fast: '0.2s'
  easing-standard: 'cubic-bezier(0.4, 0, 0.2, 1)'
components:
  button-primary:
    bg: 'linear-gradient(135deg, {colors.primary-gradient-start} 0%, {colors.primary-gradient-end} 100%)'
    text: '{colors.text-inverse}'
    radius: '{radius.sm}'
    padding: '10px 16px'
    font-weight: 500
  card:
    bg: '{colors.surface}'
    radius: '{radius.sm}'
    shadow: '{elevation.card}'
  input:
    bg: '{colors.surface}'
    border: '1px solid {colors.border-subtle}'
    radius: '{radius.sm}'
    padding: '10px 16px'
    text: '{colors.text-primary}'
    placeholder: '{colors.text-muted}'
---

# Design System Inspired by LUANAR SARIS Login

## 1. Visual Theme & Atmosphere

The LUANAR SARIS login page presents a clean, centered interface with a focus on form clarity and a subtle brand presence. The overall atmosphere is professional and straightforward, utilizing a soft, light blue-gray background `#e2e8f0` that provides a calming contrast to the central white `#ffffff` login card. Typography is consistently set in the Inter font, with a prominent `24px` `700` weight heading for "Welcome Back!". Interactive elements, such as the "Sign In" button, feature a diagonal gradient from `#764ba2` to `#667eea`, adding a touch of modern vibrancy.

Subtle micro-interactions enhance usability, with input fields and buttons exhibiting `transform: translateY(-1px)` and `box-shadow` changes on hover, along with a distinct focus ring `rgba(102, 126, 234, 0.1)` for form inputs. The layout is highly centralized, guiding the user's attention directly to the login form. The design prioritizes clear information hierarchy and accessible interaction states, with a minimal use of decorative elements beyond the brand's emblem.

Key Characteristics:
- Soft `#e2e8f0` background with a prominent `#ffffff` central card.
- Inter font family for all text elements, emphasizing legibility.
- Gradient primary button from `#764ba2` to `#667eea`.
- Rounded corners `8px` on inputs and buttons for a friendly feel.
- Subtle `translateY(-1px)` and `box-shadow` animations on hover.
- Clear `rgba(102, 126, 234, 0.1)` focus ring on interactive inputs.
- Centered layout with ample vertical `48px` spacing around the card.

## 2. Color Palette & Roles

-   **Primary**
    -   `primary-gradient-start` (`#764ba2`) — The starting color for the primary button gradient and the hover state for interactive links.
    -   `primary-gradient-end` (`#667eea`) — The ending color for the primary button gradient, creating a smooth transition from purple to blue.

-   **Accent Colors**
    -   `error-strong` (`#dc2626`) — Used for critical error messages and required field indicators.
    -   `error-light` (`#ef4444`) — A slightly lighter shade of red, used for less critical error text or warnings.

-   **Interactive**
    -   `link-hover` (`#764ba2`) — The color applied to text links on hover, matching the primary gradient start for consistency.
    -   `focus-ring-shadow` (`rgba(102, 126, 234, 0.1)`) — The subtle blue tint used for the focus ring shadow around interactive elements.

-   **Neutral Scale**
    -   `text-heading` (`#111827`) — The darkest text color, reserved for primary headings and high-emphasis text like "Welcome Back!".
    -   `text-primary` (`#000000`) — Standard black text for general body content and input values.
    -   `text-secondary` (`#374151`) — Used for form labels and secondary informational text.
    -   `text-muted` (`#9ca3af`) — Applied to placeholder text within inputs and tertiary information.
    -   `text-inverse` (`#ffffff`) — White text used on dark or colored backgrounds, such as primary buttons.
    -   `background` (`#e2e8f0`) — The light blue-gray color used for the main page background.

-   **Surface & Borders**
    -   `surface` (`#ffffff`) — The clean white background used for cards and input fields.
    -   `border-subtle` (`#e5e7eb` (inferred from screenshot)) — A light gray used for input field borders to provide subtle definition.

## 3. Typography Rules

-   **Font Family**: `Inter`, `ui-sans-serif`, `sans-serif`, `system-ui`
-   **Hierarchy**:
    -   **Display/H1**: `Inter` `24px` `700` · line-height `1.2` · tracking `none` · Used for prominent page titles like "Welcome Back!".
    -   **Body**: `Inter` `16px` `400` · line-height `1.5` · tracking `none` · Standard text for paragraphs and general information.
    -   **Small**: `Inter` `14px` `400` · line-height `1.5` · tracking `none` · Used for form labels, secondary text, and links.
-   **Principles**
    -   Prioritize legibility and clarity with the sans-serif `Inter` typeface across all text elements.
    -   Maintain a clear visual hierarchy by reserving `700` weight for headings and `400` for body text.
    -   Use `14px` for labels and secondary information to distinguish them from primary body content.
    -   Ensure consistent line-heights of `1.5` for body and `1.2` for display text to optimize readability.

## 4. Component Stylings

### Buttons

**Primary Button**
A prominent call-to-action button with a purple-to-blue gradient background, white text, and rounded corners. It animates with a slight lift and shadow expansion on hover, and dims when disabled.

```css
.login-button {
  background: linear-gradient(135deg, var(--color-primary-gradient-start, #764ba2) 0%, var(--color-primary-gradient-end, #667eea) 100%);
  color: var(--color-text-inverse, #ffffff);
  font-family: 'Inter', ui-sans-serif, sans-serif;
  font-size: 14px; /* Extracted from button text */
  font-weight: 500;
  padding: 10px 16px;
  border: none;
  border-radius: var(--radius-sm, 8px);
  cursor: pointer;
  transition: transform var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              box-shadow var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1));
}

.login-button:hover {
  transform: translateY(-1px);
  box-shadow: var(--elevation-hover, rgba(102, 126, 234, 0.25) 0px 8px 25px);
}

.login-button:active {
  transform: translateY(0);
  box-shadow: none; /* inferred from screenshot */
  background: linear-gradient(135deg, var(--color-primary-gradient-end, #667eea) 0%, var(--color-primary-gradient-start, #764ba2) 100%); /* inferred from screenshot */
}

.login-button:disabled {
  cursor: default;
  opacity: 0.6; /* inferred from screenshot */
  background: linear-gradient(135deg, var(--color-primary-gradient-start, #764ba2) 0%, var(--color-primary-gradient-end, #667eea) 100%);
  transform: none;
  box-shadow: none;
}
```

**Secondary Button** (Not explicitly visible, but inferred as a common variant for supporting actions.)
A button with a subtle border and transparent background, suitable for less emphasized actions.

```css
.button-secondary {
  background-color: transparent;
  color: var(--color-text-secondary, #374151); /* inferred from screenshot */
  font-family: 'Inter', ui-sans-serif, sans-serif;
  font-size: 14px; /* inferred from screenshot */
  font-weight: 500; /* inferred from screenshot */
  padding: 10px 16px;
  border: 1px solid var(--color-border-subtle, #e5e7eb); /* inferred from screenshot */
  border-radius: var(--radius-sm, 8px);
  cursor: pointer;
  transition: background-color var(--motion-duration-fast, 0.2s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              border-color var(--motion-duration-fast, 0.2s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              color var(--motion-duration-fast, 0.2s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1));
}

.button-secondary:hover {
  background-color: var(--color-background, #e2e8f0); /* inferred from screenshot */
  border-color: var(--color-primary-gradient-start, #764ba2); /* inferred from screenshot */
  color: var(--color-primary-gradient-start, #764ba2); /* inferred from screenshot */
}

.button-secondary:active {
  background-color: var(--color-background, #e2e8f0); /* inferred from screenshot */
  border-color: var(--color-primary-gradient-end, #667eea); /* inferred from screenshot */
  color: var(--color-primary-gradient-end, #667eea); /* inferred from screenshot */
}

.button-secondary:disabled {
  cursor: default;
  opacity: 0.5; /* inferred from screenshot */
  background-color: transparent;
  border-color: var(--color-border-subtle, #e5e7eb);
  color: var(--color-text-muted, #9ca3af);
}
```

**Ghost Button** (Not explicitly visible, but inferred as a common variant for low-emphasis actions.)
A text-only button, often used for secondary actions or links within a form.

```css
.button-ghost {
  background: none;
  color: var(--color-text-secondary, #374151); /* inferred from screenshot */
  font-family: 'Inter', ui-sans-serif, sans-serif;
  font-size: 14px; /* inferred from screenshot */
  font-weight: 400; /* inferred from screenshot */
  padding: 8px 12px; /* inferred from screenshot */
  border: none;
  border-radius: var(--radius-sm, 8px);
  cursor: pointer;
  transition: color var(--motion-duration-fast, 0.2s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              background-color var(--motion-duration-fast, 0.2s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1));
}

.button-ghost:hover {
  color: var(--color-link-hover, #764ba2);
  background-color: var(--color-background, #e2e8f0); /* inferred from screenshot */
}

.button-ghost:active {
  color: var(--color-primary-gradient-end, #667eea); /* inferred from screenshot */
  background-color: var(--color-background, #e2e8f0); /* inferred from screenshot */
}

.button-ghost:disabled {
  cursor: default;
  opacity: 0.5; /* inferred from screenshot */
  color: var(--color-text-muted, #9ca3af);
  background: none;
}
```

### Cards & Containers

**Standard Card**
A white, rounded container with a distinct shadow, used for the main login form. On hover, it subtly lifts and its shadow expands, mimicking the input field hover effect.

```css
.modern-card {
  background-color: var(--color-surface, #ffffff);
  border-radius: var(--radius-sm, 8px);
  box-shadow: var(--elevation-card, rgba(0, 0, 0, 0.25) 0px 25px 50px -12px);
  padding: 32px; /* inferred from screenshot */
  transition: transform var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              box-shadow var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1));
}

.modern-card:hover {
  transform: translateY(-1px); /* inferred from screenshot */
  box-shadow: var(--elevation-hover, rgba(102, 126, 234, 0.25) 0px 8px 25px); /* inferred from screenshot */
}
```

### Inputs & Forms

**Text Input**
Standard text input fields with a subtle border, rounded corners, and placeholder text. They feature a distinct focus state with a gradient background, shadow, and focus ring, along with a slight lift.

```css
.form-input {
  background-color: var(--color-surface, #ffffff);
  color: var(--color-text-primary, #000000);
  font-family: 'Inter', ui-sans-serif, sans-serif;
  font-size: 16px; /* Extracted */
  font-weight: 400; /* Extracted */
  padding: 10px 16px; /* Extracted */
  border: 1px solid var(--color-border-subtle, #e5e7eb); /* inferred from screenshot */
  border-radius: var(--radius-sm, 8px);
  width: 100%;
  box-sizing: border-box;
  transition: background-color var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              border-color var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              box-shadow var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              transform var(--motion-duration-base, 0.3s) var(--motion-easing-standard, cubic-bezier(0.4, 0, 0.2, 1));
}

.form-input::placeholder {
  color: var(--color-text-muted, #9ca3af);
}

.form-input:hover {
  box-shadow: var(--focus-ring-shadow, rgba(102, 126, 234, 0.1)) 0px 4px 12px;
  transform: translateY(-1px);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary-gradient-end, #667eea); /* inferred from screenshot */
  box-shadow: var(--focus-ring-shadow, rgba(102, 126, 234, 0.1)) 0px 0px 0px 3px, rgba(102, 126, 234, 0.15) 0px 8px 25px;
  transform: translateY(-2px);
  background-image: linear-gradient(135deg, rgb(255, 255, 255) 0%, rgb(240, 244, 255) 100%);
  background-color: initial;
}

.form-input:disabled {
  cursor: default;
  background-color: var(--color-background, #e2e8f0); /* inferred from screenshot */
  border-color: var(--color-border-subtle, #e5e7eb);
  color: var(--color-text-muted, #9ca3af);
  transform: none;
  box-shadow: none;
}
```

**Form Label**
Labels for input fields, using a slightly darker text color and smaller font size than body text.

```css
.form-label {
  display: block;
  color: var(--color-text-secondary, #374151);
  font-family: 'Inter', ui-sans-serif, sans-serif;
  font-size: 14px; /* Extracted */
  font-weight: 500; /* Extracted */
  margin-bottom: var(--spacing-8, 8px);
}
```

**Checkbox/Radio**
(None observed in source)

### Navigation

**Navigation Link** (Applies to "Forgot Password?" and "Contact IT Support")
Standard text links, underlined on hover, with a color change to the primary purple.

```css
.modern-link {
  color: var(--color-text-secondary, #374151); /* inferred from screenshot */
  font-family: 'Inter', ui-sans-serif, sans-serif;
  font-size: 14px; /* Extracted */
  font-weight: 400; /* Extracted */
  text-decoration: none;
  transition: color var(--motion-duration-fast, 0.2s) linear,
              text-decoration-color var(--motion-duration-fast, 0.2s) linear; /* inferred from screenshot */
}

.modern-link:hover {
  color: var(--color-link-hover, #764ba2);
  text-decoration: underline; /* inferred from screenshot */
  text-decoration-color: var(--color-link-hover, #764ba2); /* inferred from screenshot */
}

.modern-link:visited {
  color: var(--color-text-secondary, #374151); /* inferred from screenshot */
}

.modern-link.active,
.modern-link[aria-current="page"] {
  color: var(--color-primary-gradient-start, #764ba2); /* inferred from screenshot */
  font-weight: 500; /* inferred from screenshot */
}
```

### Links

**Standard Link** (Similar to Navigation Link, used for "Forgot Password?" and "Contact IT Support")
A functional link designed for inline or secondary actions, changing color and underlining on hover.

```css
.standard-link {
  color: var(--color-text-secondary, #374151);
  font-family: 'Inter', ui-sans-serif, sans-serif;
  font-size: 14px;
  font-weight: 400;
  text-decoration: none;
  transition: color var(--motion-duration-fast, 0.2s) linear,
              text-decoration-color var(--motion-duration-fast, 0.2s) linear;
}

.standard-link:hover {
  color: var(--color-link-hover, #764ba2);
  text-decoration: underline;
  text-decoration-color: var(--color-link-hover, #764ba2);
}

.standard-link:visited {
  color: var(--color-text-secondary, #374151); /* inferred from screenshot */
}
```

**Secondary Link**
(None observed in source)

### Badges

(None observed in source)

## 5. Layout Principles

-   **Spacing System**: Base `4px` → `8`, `12`, `16`, `24`, `32`, `48`
    -   `8px`: Smallest internal spacing, e.g., between form label and input.
    -   `12px`: Padding within smaller components or between inline elements.
    -   `16px`: Standard vertical spacing between form elements or horizontal padding.
    -   `24px`: Moderate spacing for grouping related elements.
    -   `32px`: Internal padding for cards or sections, creating breathing room.
    -   `48px`: Large vertical spacing, used for separating major content blocks like the card from the header/footer.
-   **Grid & Container** _Note: container widths and column counts are not extracted from the source. The values below are reasonable defaults inferred from the visible layout density._
    -   Max Width: `480px` (inferred from screenshot) for the central card to maintain focus.
    -   Columns: `1` (inferred from screenshot) for the main content area.
    -   Gutter: `24px` (inferred from screenshot) between potential columns on wider screens.
    -   Section Padding: `48px` `0` (inferred from screenshot) for vertical spacing around the central card.
-   **Whitespace Philosophy**: The design employs generous whitespace, particularly around the central login card, to create a sense of calm and direct user focus. Elements within the card are well-spaced using `8px` to `16px` increments, ensuring visual separation without feeling disconnected. This ample use of negative space contributes to the clean and professional aesthetic.
-   **Border Radius Scale**:
    -   `sm`: `8px` — Applied to primary buttons, input fields, and the main login card for a soft, approachable feel.
    -   `md`: `12px` — Used for larger containers or elements requiring a slightly more pronounced curve (not explicitly visible, but inferred for consistency).

## 6. Depth & Elevation

-   **Flat (z-0)**: `none` — Used for the main page background and non-interactive elements.
-   **Card (z-1)**: `rgba(0, 0, 0, 0.25) 0px 25px 50px -12px` — Applied to the central login card to lift it distinctly from the background, indicating it as a primary content area.
-   **Hover (z-2)**: `rgba(102, 126, 234, 0.25) 0px 8px 25px` — Used for interactive elements like input fields and buttons on hover, providing a subtle visual feedback of interaction.
-   **Focus (z-3)**: `rgba(102, 126, 234, 0.15) 0px 8px 25px` (inferred from screenshot) — Combined with a smaller inner shadow for focus states, indicating active interaction.

Shadow Philosophy: The design uses shadows sparingly but effectively to create a clear sense of hierarchy and interactivity. A deep, diffused shadow `#000000` `0.25` is applied to the main card to establish its prominence. Lighter, more focused shadows `rgba(102, 126, 234, 0.25)` are employed for interactive states, signaling user engagement and providing a subtle lift to elements like inputs and buttons.

## 7. Do's and Don'ts

### Do's
-   Use `Inter` `24px` `700` for primary headings like "Welcome Back!" to ensure strong visual impact.
-   Apply the gradient from `{colors.primary-gradient-start}` to `{colors.primary-gradient-end}` for all primary buttons.
-   Ensure form labels use `{colors.text-secondary}` (`#374151`) and are `14px` `500` weight for clear distinction.
-   Maintain `8px` border-radius (`{radius.sm}`) on all input fields and primary buttons for a consistent soft aesthetic.
-   Place at least `16px` of vertical spacing (`{spacing.16}`) between form input fields for readability.
-   Use `{colors.error-strong}` (`#dc2626`) for critical error messages, ensuring high visibility.
-   Implement `transform: translateY(-1px)` and `{elevation.hover}` shadow on the Primary Button and Text Input `:hover` states.
-   Ensure text links like "Forgot Password?" use `{colors.link-hover}` (`#764ba2`) on hover, with `text-decoration: underline`.
-   Use `{colors.text-primary}` (`#000000`) on `{colors.surface}` (`#ffffff`) for body text, achieving an AAA contrast ratio of 21:1.
-   Ensure `{colors.text-secondary}` (`#374151`) on `{colors.surface}` (`#ffffff`) for labels passes AAA with a ratio of 10.31:1.

### Don'ts
-   Avoid using `16px` font size for form labels; reserve `14px` `500` for this role.
-   Do not use `#000000` for placeholder text; instead, use `{colors.text-muted}` (`#9ca3af`) for lower visual hierarchy.
-   Never apply the primary button gradient to secondary or ghost buttons; use their defined styles.
-   Do not introduce custom spacing values; adhere strictly to the `{spacing.scale}` of `8`, `12`, `16`, `24`, `32`, `48` px.
-   Avoid using `{elevation.card}` shadow on hover states; `{elevation.hover}` is specifically designed for interaction feedback.
-   Do not use `{colors.error-light}` (`#ef4444`) for critical error messages; reserve `{colors.error-strong}` (`#dc2626`) for this.
-   Do not remove the `outline: none` and `box-shadow` focus ring from `{components.input}` `:focus` state.
-   Never use `{colors.error-light}` (`#ef4444`) on `{colors.surface}` (`#ffffff`) for body text, as its 3.76:1 ratio only passes AA-large, not standard AA.
-   Do not apply `font-weight: 700` to body text; reserve this for `{typography.display}`.
-   Avoid placing elements closer than `{spacing.8}` (`8px`) to each other to maintain clear visual separation.

## 8. Responsive Behavior

_Note: breakpoints below are industry-standard recommendations, not measurements from the source. Adjust to the brand's actual media queries when implementing._

-   **Suggested Breakpoints**:
    -   **Mobile Small** (~320px): Card padding reduces, font sizes scale down slightly for optimal fit.
    -   **Mobile Large** (~640px): Main content card width adjusts to `min-width: 640px` to fill more screen.
    -   **Tablet** (~768px): Layout remains centered, potentially wider card and more generous padding.
    -   **Desktop** (~1024px): Layout maintains `min-width: 1024px` for full desktop experience.
    -   **Desktop Large** (~1440px): Max width of the central card might increase slightly for larger screens.
-   **Touch Targets**:
    -   Ensure all interactive elements like buttons and links have a minimum touch target area of `44px` by `44px` (inferred from best practices).
    -   Maintain at least `8px` (`{spacing.8}`) clear space between touch targets to prevent accidental taps.
-   **Collapsing Strategy**:
    -   **Cards**: The central login card should scale its width to `90%` of the viewport on mobile, with horizontal padding `16px` (`{spacing.16}`).
    -   **Typography**: `Display` (`24px`) font size should remain consistent, but `Body` and `Small` text may reduce to `14px` and `12px` respectively on mobile (inferred from best practices).
    -   **Padding**: Vertical section padding (`{spacing.48}`) should be maintained where possible, but horizontal padding on the card can reduce to `24px` (`{spacing.24}`) on smaller viewports.
    -   **Forms**: Input fields should maintain `100%` width within their container, stacking vertically for optimal mobile usability.
    -   **Spacing**: General spacing `8px` (`{spacing.8}`) and `16px` (`{spacing.16}`) should be prioritized on mobile to conserve vertical screen real estate.

## 9. Agent Prompt Guide

-   **Quick Color Reference**
    -   `primary-gradient-start`: `#764ba2`
    -   `primary-gradient-end`: `#667eea`
    -   `background`: `#e2e8f0`
    -   `surface`: `#ffffff`
    -   `text-heading`: `#111827`
    -   `text-primary`: `#000000`
    -   `text-secondary`: `#374151`
    -   `text-muted`: `#9ca3af`
    -   `text-inverse`: `#ffffff`
    -   `border-subtle`: `#e5e7eb`
    -   `error-strong`: `#dc2626`
    -   `error-light`: `#ef4444`
    -   `link-hover`: `#764ba2`
    -   `focus-ring-shadow`: `rgba(102, 126, 234, 0.1)`

-   **Iteration Guide**
    1.  Always use `Inter` as the primary font family for all text elements.
    2.  Set `font-size: 24px` with `font-weight: 700` for all primary headings.
    3.  Apply `font-size: 16px` with `font-weight: 400` for standard body text.
    4.  Utilize the spacing scale: `8px`, `12px`, `16px`, `24px`, `32px`, `48px` for all layout and component spacing.
    5.  Ensure all interactive elements (buttons, inputs) have a `border-radius` of `8px`.
    6.  Primary Buttons must use the `linear-gradient(135deg, #764ba2 0%, #667eea 100%)` background with `#ffffff` text.
    7.  Inputs should have a `1px solid #e5e7eb` border and `padding: 10px 16px`.
    8.  Implement `:hover` states with `transform: translateY(-1px)` and `box-shadow: rgba(102, 126, 234, 0.25) 0px 8px 25px` for buttons and cards.
    9.  Input `:focus` states require an `outline: none`, `border-color: #667eea`, and `box-shadow: rgba(102, 126, 234, 0.1) 0px 0px 0px 3px, rgba(102, 126, 234, 0.15) 0px 8px 25px`.
    10. Cards should always use a `#ffffff` background and `box-shadow: rgba(0, 0, 0, 0.25) 0px 25px 50px -12px`.
    11. Ensure all text on `#ffffff` backgrounds meets WCAG AA contrast standards; specifically, `#374151` on `#ffffff` (10.31:1) is acceptable.
    12. On mobile, the central card should adapt to `90%` width with horizontal `padding: 16px`.