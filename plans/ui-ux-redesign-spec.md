# UI/UX Redesign Specification — BankMatch Financial Copilot

**Version:** 1.0
**Date:** 2026-07-28
**Status:** Draft
**Scope:** Sidebar Navigation, Reporting Page Header, Reporting Page Layout, Component & Aesthetic Overhaul

---

## Table of Contents

1. [Overview](#overview)
2. [Requirement 1: Sidebar Navigation Refinement](#requirement-1-sidebar-navigation-refinement)
3. [Requirement 2: Header Modification](#requirement-2-header-modification)
4. [Requirement 3: Reporting Page Layout Optimization](#requirement-3-reporting-page-layout-optimization)
5. [Requirement 4: Component & Aesthetic Overhaul](#requirement-4-component--aesthetic-overhaul)
6. [Design Token Updates](#design-token-updates)
7. [Implementation Notes](#implementation-notes)

---

## Overview

This specification defines a comprehensive UI/UX redesign for the BankMatch Financial Copilot application. The redesign focuses on four key areas: simplifying the sidebar navigation, updating the Reporting page header, optimizing the Reporting page layout for maximum screen utility, and performing a full component and aesthetic overhaul to achieve a modern, sophisticated, and cohesive professional interface.

The application is built with **Angular 18** using standalone components, CSS custom properties for theming, and a custom design system (no external CSS framework). All changes are scoped to the frontend under `frontend/src/app/`.

---

## Requirement 1: Sidebar Navigation Refinement

### Objective

Simplify the sidebar by removing all navigation items except **"AI Copilot"** and **"Reporting."** The "Benchmarking" link and all other existing navigation items must be removed.

### Current State

The sidebar is defined in `frontend/src/app/core/layout/layout.component.ts` (lines 16-24) with the following `navItems` array:

| Icon | Label | Route |
|------|-------|-------|
| `dashboard` | Dashboard | `/dashboard` |
| `receipt` | Transactions | `/transactions` |
| `compare` | Reconciliation | `/reconciliation` |
| `smart_toy` | AI Assistant | `/copilot` |
| `science` | Benchmark Lab | `/benchmark` |
| `bar_chart` | Reports | `/reporting` |
| `settings` | Settings | `/settings` |

The sidebar template is in `frontend/src/app/core/layout/layout.component.html` (lines 16-58), which iterates over `navItems` with `*ngFor` and renders SVG icons for each item.

### Target State

The `navItems` array must be reduced to exactly two entries:

| Icon | Label | Route |
|------|-------|-------|
| `smart_toy` | AI Copilot | `/copilot` |
| `bar_chart` | Reporting | `/reporting` |

### Changes Required

#### 1.1 `layout.component.ts`

Replace the `navItems` array (lines 16-24) with:

```typescript
navItems = [
  { icon: 'smart_toy', label: 'AI Copilot', route: '/copilot', active: false },
  { icon: 'bar_chart', label: 'Reporting', route: '/reporting', active: false },
];
```

**Rationale:** Removes Dashboard, Transactions, Reconciliation, Benchmark Lab, and Settings. Retains only AI Copilot and Reporting with their existing icon identifiers and routes.

#### 1.2 `layout.component.html`

No structural HTML changes are required. The `*ngFor` loop over `navItems` will automatically render only the two remaining items. The SVG icon templates for `smart_toy` and `bar_chart` (already present at lines 39-54) will continue to work as-is.

However, the SVG icon for the label **"AI Assistant"** (currently used for the copilot route) should be updated to **"AI Copilot"** to match the new label. The icon itself (`smart_toy`) remains the same; only the text label changes in the TypeScript data.

#### 1.3 `layout.component.css`

No CSS changes are required for this requirement. The existing sidebar styles accommodate any number of nav items.

### Edge Cases

- The `routerLinkActive` directive on each nav item will continue to work correctly with only two items.
- The sidebar collapse/expand toggle and user info section at the bottom remain unchanged.
- If the app has hardcoded references to the removed routes (`/dashboard`, `/transactions`, `/reconciliation`, `/benchmark`, `/settings`) elsewhere in the codebase, those references should be audited and removed or redirected. See `app.routes.ts` for route cleanup guidance.

---

## Requirement 2: Header Modification

### Objective

On the Reporting page, update the header text. Replace the current **"AI Assistant"** label with **"Reporting & Analytics"** or a professional equivalent that better reflects the page's purpose.

### Current State

The header text "AI Assistant" is defined in `frontend/src/app/core/layout/layout.component.html` at line 83:

```html
<h1 class="page-title">AI Assistant</h1>
```

This is a static heading in the topbar that applies globally to all pages rendered within the layout. It does not dynamically change per route.

### Target State

The header should display a context-appropriate title. For the Reporting page, it should show **"Reporting & Analytics"**. For other pages (AI Copilot), it should show an appropriate title.

### Changes Required

#### 2.1 `layout.component.ts`

Add a `currentPageTitle` property that dynamically reflects the active route:

```typescript
currentPageTitle: string = 'AI Copilot';
```

Add a method to update the title based on the current route:

```typescript
updatePageTitle(): void {
  const route = this.router.url;
  if (route.startsWith('/reporting')) {
    this.currentPageTitle = 'Reporting & Analytics';
  } else if (route.startsWith('/copilot')) {
    this.currentPageTitle = 'AI Copilot';
  } else {
    this.currentPageTitle = 'BankMatch';
  }
}
```

Inject `Router` and subscribe to route changes in the constructor or `ngOnInit` to call `updatePageTitle()`.

#### 2.2 `layout.component.html`

Replace the static heading at line 83:

```html
<h1 class="page-title">{{ currentPageTitle }}</h1>
```

### Alternative Approach (Simpler)

If dynamic route-based titles are not desired, a simpler approach is to set the title directly in the Reporting shell component and use a shared service or `@Input` binding. However, the dynamic approach above is the most maintainable and scalable.

### Edge Cases

- The `page-title` CSS class (line 227-232 of `layout.component.css`) already styles the heading appropriately; no CSS changes needed.
- The topbar header height (64px) and padding (0 28px) remain unchanged.

---

## Requirement 3: Reporting Page Layout Optimization

### Objective

Streamline the Reporting page by removing the introductory text block that contains the title "Reporting & Analytics" and the description "Financial insights, KPI dashboards, and report management." The page layout should transition immediately into the functional tools and data elements to maximize screen real estate and utility.

### Current State

The Reporting page header and introductory text block is defined in `frontend/src/app/modules/reporting/pages/reporting-shell/reporting-shell.component.html` (lines 1-17):

```html
<div class="reporting-shell">
  <!-- Header -->
  <header class="reporting-header">
    <div class="header-brand">
      <div class="header-icon">
        <svg ...>...</svg>
      </div>
      <div class="header-text">
        <h1>Reporting & Analytics</h1>
        <p class="header-subtitle">Financial insights, KPI dashboards, and report management</p>
      </div>
    </div>
  </header>

  <!-- Navigation Tabs -->
  <nav class="reporting-nav">...</nav>

  <!-- Content Area -->
  <div class="reporting-content">
    <router-outlet></router-outlet>
  </div>
</div>
```

The corresponding styles are in `reporting-shell.component.css` (lines 8-42 for the header, lines 45-86 for the nav).

### Target State

Remove the entire `<header class="reporting-header">` block (lines 3-17 of the HTML). The page should transition directly from the shell container into the navigation tabs, and then into the content area. The navigation tabs remain as the primary way to switch between Analytics, Reports, and Templates views.

### Changes Required

#### 3.1 `reporting-shell.component.html`

Remove lines 3-17 (the entire `reporting-header` block). The resulting structure:

```html
<div class="reporting-shell">
  <!-- Navigation Tabs -->
  <nav class="reporting-nav">
    <a
      *ngFor="let tab of navTabs"
      [routerLink]="tab.route"
      routerLinkActive="active"
      [routerLinkActiveOptions]="{ exact: false }"
      class="nav-tab"
    >
      <span class="nav-icon" [innerHTML]="tab.icon"></span>
      <span class="nav-label">{{ tab.label }}</span>
    </a>
  </nav>

  <!-- Content Area -->
  <div class="reporting-content">
    <router-outlet></router-outlet>
  </div>
</div>
```

#### 3.2 `reporting-shell.component.css`

Remove the `.reporting-header`, `.header-brand`, `.header-icon`, `.header-text`, `.header-subtitle` styles (lines 8-42).

Adjust the `.reporting-nav` padding and background to account for the removed header. The nav should now be the topmost visual element:

```css
.reporting-nav {
  display: flex;
  gap: 0;
  padding: 0 32px;
  background: #1a1a2e;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
```

Adjust the `.reporting-content` min-height to account for the reduced total height:

```css
.reporting-content {
  padding: 0;
  min-height: calc(100vh - 136px);
  background: #f8fafc;
}
```

The `136px` value accounts for the nav height (~48px) plus remaining spacing. Adjust as needed after implementation.

#### 3.3 `reporting-shell.component.ts`

No TypeScript changes are required. The `navTabs` array remains unchanged.

### Edge Cases

- The `reporting-shell.component.css` responsive media queries (lines 96-114) reference `.reporting-header` padding — these should be removed since the header is deleted.
- The `reporting-content` background color (`#f8fafc`) should remain consistent with the overall page background.
- The navigation tabs retain their dark background (`#1a1a2e`) and accent underline styling, which provides clear visual separation from the content area below.

---

## Requirement 4: Component & Aesthetic Overhaul

### Objective

Perform a comprehensive design upgrade for the entire Reporting page. This includes:
- **Custom Tab Styling**: Replace the default system-style tab components with a modern, polished, custom-designed aesthetic.
- **Visual Design Language**: Move away from generic layouts toward a sophisticated, modern, and cohesive user interface that enhances professional usability.

### 4.1 Custom Tab Styling

#### Current State

The tabs in `reporting-shell.component.html` (lines 20-31) use basic `<a>` tags with `routerLinkActive` for active state. The CSS in `reporting-shell.component.css` (lines 45-86) styles them with:
- A dark background (`#1a1a2e`)
- White text at 60% opacity
- A bottom border accent on active state (`#818cf8`)
- Simple padding and font styling

#### Target State

Replace the current tab design with a modern, custom-styled tab component that includes:

**Visual Design:**
- **Active indicator**: A pill-shaped highlight (not just a bottom border) with a subtle gradient background
- **Hover state**: Smooth color transition with a light background wash
- **Inactive state**: Muted text color, no background
- **Icons**: Slightly larger icons (20px) with a subtle shadow or glow on active state
- **Spacing**: Generous padding (12px 24px) with rounded corners (8px) on the active tab
- **Animation**: Smooth transitions (0.25s ease) for all state changes
- **Font**: Use the Inter font family (already loaded globally), 13px, font-weight 500 for inactive, 600 for active

**HTML Changes (`reporting-shell.component.html`):**

Replace the `<nav class="reporting-nav">` block with:

```html
<nav class="reporting-nav">
  <a
    *ngFor="let tab of navTabs"
    [routerLink]="tab.route"
    routerLinkActive="active"
    [routerLinkActiveOptions]="{ exact: false }"
    class="nav-tab"
  >
    <span class="nav-icon" [innerHTML]="tab.icon"></span>
    <span class="nav-label">{{ tab.label }}</span>
  </a>
</nav>
```

The HTML structure remains the same; all visual changes are in CSS.

**CSS Changes (`reporting-shell.component.css`):**

Replace the `.reporting-nav` and `.nav-tab` styles with:

```css
.reporting-nav {
  display: flex;
  gap: 6px;
  padding: 8px 32px;
  background: transparent;
  border-bottom: 1px solid var(--border-hairline);
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  white-space: nowrap;
}

.nav-tab:hover {
  color: var(--text-heading);
  background: var(--bg-page);
  border-color: var(--border-hairline);
}

.nav-tab.active {
  color: #ffffff;
  background: linear-gradient(135deg, var(--brand-primary), #6366f1);
  border-color: transparent;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(47, 95, 224, 0.35);
}

.nav-tab.active .nav-icon {
  filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.4));
}

.nav-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
}

.nav-label {
  white-space: nowrap;
}
```

**Key Design Decisions:**
- The nav background is now transparent with a subtle bottom border instead of the dark header band
- Active tab uses a gradient (brand primary to indigo) with a box shadow for depth
- Hover state uses the page background color with a border for definition
- The gap between tabs (6px) creates breathing room
- The active tab has a drop-shadow filter on its icon for a subtle glow effect

---

### 4.2 Visual Design Language Overhaul

#### 4.2.1 Reporting Shell Container

**Current:** `reporting-shell.component.css` uses `padding: 0` and `max-width: 100%`.

**Target:** Add a subtle max-width constraint and center the content for a more refined, focused layout:

```css
.reporting-shell {
  padding: 0;
  max-width: 1440px;
  margin: 0 auto;
}
```

#### 4.2.2 Content Area

**Current:** `.reporting-content` has `background: #f8fafc` with no padding.

**Target:** Add subtle padding and a card-like container feel:

```css
.reporting-content {
  padding: 24px 32px;
  min-height: calc(100vh - 136px);
  background: var(--bg-page);
}
```

#### 4.2.3 Reporting Dashboard Page

**File:** `reporting-dashboard.component.css`

**Current issues:**
- Generic card borders with `#e5e7eb`
- Basic stat cards with no visual hierarchy
- Table styling is functional but lacks polish
- Modal styling is basic

**Target upgrades:**

1. **Stats Bar**: Replace flat stat cards with glass-morphism-style cards:
   - Background: `rgba(255, 255, 255, 0.8)` with `backdrop-filter: blur(12px)`
   - Border: `1px solid rgba(255, 255, 255, 0.6)`
   - Box shadow: `0 4px 24px rgba(0, 0, 0, 0.06)`
   - Add a subtle top accent line (3px) using a gradient per card

2. **Reports Table**: 
   - Replace the basic table with a card-list design for better mobile responsiveness
   - Each report becomes a card with hover elevation
   - Status badges get improved styling with softer colors and rounded pill shapes
   - Action buttons use icon-only buttons with tooltips instead of emoji

3. **Workspace Header**: 
   - Add a subtle gradient background or a soft colored accent bar at the top
   - Improve typography hierarchy with better spacing

4. **Modal**: 
   - Increase border-radius to 16px
   - Add a subtle backdrop blur
   - Improve form field styling with better focus states

#### 4.2.4 Analytics Workspace Page

**File:** `analytics-workspace.component.css`

**Current issues:**
- KPI cards are functional but lack visual distinction
- Chart cards have basic borders
- Filter bar is generic

**Target upgrades:**

1. **KPI Strip**: 
   - Each KPI card gets a unique accent color based on its metric type
   - Add a subtle gradient background per card
   - Increase the hover lift effect (translateY -3px, stronger shadow)
   - Add a colored top bar (3px) matching the metric's category color

2. **Chart Cards**:
   - Add a subtle inner shadow for depth
   - Increase border-radius to 16px
   - Add a soft header area for chart titles
   - Improve the chart container spacing

3. **Filter Bar**:
   - Add a subtle glass-morphism effect
   - Improve input styling with better focus rings
   - Add a subtle gradient background

#### 4.2.5 Report Builder Page

**File:** `report-builder.component.css`

**Target upgrades:**
- Modernize the tab navigation with the same custom tab styling as the Reporting shell
- Add card-based layout for section configuration
- Improve the element palette with better hover states and drag-and-drop visual cues
- Refine the modal styling to match the new design language

---

### 4.3 Global Design System Enhancements

**File:** `frontend/src/styles.css`

Add the following new design tokens to support the overhaul:

```css
/* ========== Enhanced Design Tokens ========== */

/* Gradients */
--gradient-primary: linear-gradient(135deg, #2F5FE0 0%, #6366f1 100%);
--gradient-header: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
--gradient-card: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);

/* Shadows (enhanced) */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
--shadow-md: 0 4px 16px rgba(0, 0, 0, 0.06);
--shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.08);
--shadow-xl: 0 16px 48px rgba(0, 0, 0, 0.1);

/* Transitions */
--transition-fast: 0.15s cubic-bezier(0.4, 0, 0.2, 1);
--transition-normal: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
--transition-slow: 0.35s cubic-bezier(0.4, 0, 0.2, 1);

/* Focus ring */
--focus-ring: 0 0 0 3px rgba(47, 95, 224, 0.15);

/* Card */
--card-radius: 12px;
--card-padding: 20px;
```

Update existing tokens as needed to align with the new design language.

---

## Design Token Updates

The following CSS custom properties in `frontend/src/styles.css` should be updated or added:

| Token | Current Value | New Value | Reason |
|-------|--------------|-----------|--------|
| `--brand-primary` | `#2F5FE0` | `#2F5FE0` (unchanged) | Core brand color |
| `--bg-page` | `#F7F8FA` | `#F7F8FA` (unchanged) | Page background |
| `--surface-card` | `#FFFFFF` | `#FFFFFF` (unchanged) | Card background |
| `--radius-sm` | `8px` | `8px` (unchanged) | Small radius |
| `--radius-md` | `12px` | `12px` (unchanged) | Medium radius |
| `--radius-lg` | `16px` | `16px` (unchanged) | Large radius |
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.04)` | `0 1px 3px rgba(0,0,0,0.04)` | Card shadow |
| `--gradient-primary` | *(new)* | `linear-gradient(135deg, #2F5FE0 0%, #6366f1 100%)` | Primary gradient |
| `--gradient-header` | *(new)* | `linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)` | Header gradient |
| `--transition-normal` | *(new)* | `0.25s cubic-bezier(0.4, 0, 0.2, 1)` | Standard transition |

---

## Implementation Notes

### File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| `layout.component.ts` | Modify | Reduce `navItems` to 2 entries; add dynamic page title logic |
| `layout.component.html` | Modify | Bind `currentPageTitle` to page title heading |
| `reporting-shell.component.html` | Modify | Remove header block (lines 3-17) |
| `reporting-shell.component.css` | Modify | Remove header styles; update nav styles for custom tabs; adjust content padding |
| `reporting-shell.component.ts` | No change | `navTabs` array unchanged |
| `reporting-dashboard.component.css` | Modify | Glass-morphism stat cards; improved table/card design; enhanced modal |
| `reporting-dashboard.component.html` | Modify | Replace emoji action buttons with icon buttons; improve card layout |
| `analytics-workspace.component.css` | Modify | Enhanced KPI cards with accent colors; improved chart cards; glass filter bar |
| `report-builder.component.css` | Modify | Custom tab styling; card-based layout; refined modal |
| `styles.css` | Modify | Add new design tokens (gradients, shadows, transitions, focus ring) |
| `app.routes.ts` | Optional | Remove routes for deleted sidebar items (`/dashboard`, `/transactions`, `/reconciliation`, `/benchmark`, `/settings`) |

### Testing Considerations

1. **Sidebar**: Verify that only "AI Copilot" and "Reporting" links appear in the sidebar across all viewport sizes.
2. **Header**: Verify that the Reporting page header shows "Reporting & Analytics" and the Copilot page shows "AI Copilot."
3. **Layout**: Verify that the Reporting page transitions directly into the tab navigation without the introductory text block.
4. **Tabs**: Verify that custom tab styling renders correctly for all three states (active, hover, inactive) across browsers.
5. **Responsive**: Verify all changes work correctly at breakpoints 768px and 1024px.
6. **Accessibility**: Verify that keyboard navigation, screen readers, and focus indicators work correctly with the new tab styling.

### Browser Compatibility

All CSS features used (gradients, `backdrop-filter`, `cubic-bezier`, CSS custom properties, `drop-shadow`) are supported in all modern browsers (Chrome 90+, Firefox 88+, Safari 15+, Edge 90+).

### Performance Considerations

- The custom tab styling uses only CSS transitions (no JavaScript animations).
- The `backdrop-filter` on modals may impact performance on low-end devices; consider a fallback `background: rgba(0,0,0,0.5)` without blur.
- Chart rendering (ECharts) is unchanged and already lazy-initialized.
