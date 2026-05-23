import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeSession, makeTurn, makeNote, SESSION_ID } from "./__fixtures__/mission";
import { useSessionQuery, useTurnsQuery, useNotesQuery } from "./api";

function paged<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

describe("useSessionQuery", () => {
  it("fetches the session by id", async () => {
    const session = makeSession();
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(session),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useSessionQuery(SESSION_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe(SESSION_ID);
  });

  it("is disabled when id is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useSessionQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useTurnsQuery", () => {
  it("is disabled when session id is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTurnsQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches paginated turns for a session", async () => {
    const turn = makeTurn({ index: 0 });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        HttpResponse.json(paged([turn])),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTurnsQuery(SESSION_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
    expect(result.current.data?.results[0].index).toBe(0);
  });
});

describe("useNotesQuery", () => {
  it("is disabled when session id is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useNotesQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches paginated notes for a session", async () => {
    const note = makeNote({ turn_index: 0 });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json(paged([note])),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useNotesQuery(SESSION_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
    expect(result.current.data?.results[0].note_type).toBe("hypothesis");
  });
});
