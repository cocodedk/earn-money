// Operator-facing copy that's referenced from more than one layer
// (parsers, UI primitives). Keep this module narrow — copy strings
// belong here when they're DRY'd across modules, not when they're
// local to a single component.

export const BACKEND_UNREACHABLE = "Backend unreachable";
