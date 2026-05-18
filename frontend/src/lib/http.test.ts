import { describe, it, expect } from "vitest";
import { http as msw, HttpResponse } from "msw";
import { server } from "../test/server";
import { http } from "./http";

describe("http", () => {
  it("returns parsed JSON on 2xx", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    const data = await http<{ count: number }>("/api/projects/");
    expect(data.count).toBe(0);
  });

  it("throws on non-2xx with the raw Response attached", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ detail: "Forbidden." }, { status: 403 }),
      ),
    );
    await expect(http("/api/projects/")).rejects.toMatchObject({
      response: expect.objectContaining({ status: 403 }),
    });
  });

  it("sends JSON body and content-type on POST", async () => {
    let receivedBody: unknown = null;
    server.use(
      msw.post("/api/projects/", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({ id: "u1" }, { status: 201 });
      }),
    );
    const result = await http<{ id: string }>("/api/projects/", {
      method: "POST",
      body: { name: "X", description: "Y" },
    });
    expect(result.id).toBe("u1");
    expect(receivedBody).toEqual({ name: "X", description: "Y" });
  });

  it("returns undefined on 204", async () => {
    server.use(
      msw.delete("/api/projects/u1/", () => new HttpResponse(null, { status: 204 })),
    );
    await expect(
      http("/api/projects/u1/", { method: "DELETE" }),
    ).resolves.toBeUndefined();
  });
});
