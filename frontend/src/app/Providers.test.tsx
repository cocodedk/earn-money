import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, Route, Routes } from "react-router-dom";
import { Providers } from "./Providers";

function QueryProbe() {
  const q = useQuery({ queryKey: ["x"], queryFn: () => 1 });
  return <div>q:{String(q.data ?? "...")}</div>;
}
function LocationProbe() {
  return <div>loc:{useLocation().pathname}</div>;
}

describe("Providers", () => {
  it("provides QueryClient and Router context", async () => {
    render(
      <Providers>
        <QueryProbe />
        <Routes>
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </Providers>,
    );
    expect(await screen.findByText("q:1")).toBeInTheDocument();
    expect(screen.getByText(/^loc:/)).toBeInTheDocument();
  });
});
