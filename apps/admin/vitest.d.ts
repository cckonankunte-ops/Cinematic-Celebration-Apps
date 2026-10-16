// Test-time global types. Resolved after `npm install`; harmless before.
/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />

// Mark this file as a module so TS does not treat it as a global script that
// can be `import`ed (which triggers TS2306 "not a module").
export {};
