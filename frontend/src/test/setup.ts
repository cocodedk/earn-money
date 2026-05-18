import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";
import { server } from "./server";
import { installSseMock } from "./sseMock";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => installSseMock());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
