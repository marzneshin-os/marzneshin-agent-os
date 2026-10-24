# Ponytail — Practical Ladder Examples

## Rung 1: Does this need to exist at all?
- **Request:** "Add a dark-mode toggle button and theme switcher engine to our internal CLI tool."
- **Ponytail Decision:** CLIs run in the user's terminal emulator; terminal emulator handles theming. We do nothing. Saved 200 lines and 1 dependency.

## Rung 2: Does the standard library handle it?
- **Request:** "Install `uuid` package to generate v4 UUIDs."
- **Ponytail Decision:** Use Node.js `crypto.randomUUID))`. Zero dependencies added.

## Rung 3: Does a native platform feature handle it?
- **Request:** "Install a datepicker React library and a query string parser."
- **Ponytail Decision:** Use native HTML5 `<input type="date">` and browser `new URLSearchParams(window.location.search)`.

## Rung 4: Does an already-installed dependency handle it?
- **Request:** "Add `rimraf` or `del` package to delete files during build."
- **Ponytail Decision:** We already have Node 18+ with `fs.rmSync(path, { recursive: true, force: true })`.

## Rung 5: Can it be solved in one line?
- **Request:** "Write a helper module with validation class for checking if string is valid email."
- **Ponytail Decision:** `const isValidEmail = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);`

## Rung 6: Write the strict minimum
- **Request:** "Add user preferences storage. We might support Redis, Postgres, and DynamoDB in the future."
- **Ponytail Decision:** Write a simple JSON file store (`prefs.json`). Do not build a generic multi-driver storage abstraction until a second driver is actually needed.

## Rung 7: Document the shortcut
- **Decision:** Used in-memory cache instead of distributed cache.
- **Action:** Added comment `// SHORTCUT: In-memory LRU cache used. Switch to Redis when multi-instance horizontal scaling is deployed.`
