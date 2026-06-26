# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**Pocket Heist** — a Next.js starter app built for the Claude Code Masterclass.
Product concept: tiny office-mischief "missions." Users create *heists*, assign
them to others, and track active / assigned / expired ones. ("Tiny missions.
Big office mischief.")

Current state: early scaffold. Routing, layouts, the design system, and the
test harness are in place. Most pages below the layouts are **heading-only
stubs** with no real logic, data, forms, or auth yet.

## Commands

```bash
npm run dev     # start dev server at http://localhost:3000
npm run build   # production build
npm run start   # serve the production build
npm run lint    # eslint
npm test        # vitest (watch mode by default)
```

Run a single test file: `npx vitest run tests/components/Navbar.test.tsx`

## Tech stack

- **Next.js 16** (App Router) + **React 19.2**
- **TypeScript 5**, `strict: true`, path alias `@/*` → repo root
- **Tailwind CSS v4** — configured CSS-first via the `@theme` directive in
  `app/globals.css` (no `tailwind.config.js`)
- **lucide-react** for icons
- **Vitest 4** + Testing Library + jsdom for tests

## Structure

```
app/
  layout.tsx            # root layout + metadata (no nav here by design)
  globals.css           # Tailwind v4 @theme: dark palette, Inter font, layout utils
  (public)/             # unauthenticated route group
    page.tsx            # splash; intended to redirect → /heists or /login (TODO)
    login/ signup/ preview/
  (dashboard)/          # authenticated route group
    layout.tsx          # renders <Navbar> + <main>
    heists/             # list: active / assigned / expired
      create/ [id]/     # create form + detail view
components/
  Navbar/               # logo + "Create Heist" link; uses Navbar.module.css
tests/
  components/Navbar.test.tsx
```

## Conventions

- **Route groups** separate concerns: `(public)` and `(dashboard)` each own
  their layout. Put authenticated pages under `(dashboard)`, public ones under
  `(public)`. The dashboard layout supplies the `<Navbar>`.
- **Styling**: prefer Tailwind utility classes. Define colors/fonts as theme
  tokens in `globals.css` (`@theme`) rather than hard-coding values. Use
  CSS Modules (`*.module.css`) for component-scoped styles, as `Navbar` does.
  Theme tokens: `primary` (#C27AFF), `secondary` (#FB64B6), `dark`, `success`,
  `error`, `heading`, `body`.
- **Components** live in `components/<Name>/` with a barrel `index.ts` that
  re-exports the default. Import via `@/components/<Name>`.
- **Tests** mirror source under `tests/` and query by accessible role
  (`getByRole`) over test ids.
- Use the `@/` alias for absolute imports; avoid deep relative paths.

## Notes

- `app/(public)/login/page.tsx` exports a component named `SignupPage` — a
  copy-paste leftover; the file is the login page. Rename if you touch it.
- This project is part of the larger `rnd` workspace but is the only
  TypeScript/Next.js app in it.
