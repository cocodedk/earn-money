import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { CreateTargetBody, Paginated, Target } from "../../types/api";

export const TARGETS_KEY = ["targets"] as const;

export function useTargetsQuery() {
  return useQuery({
    queryKey: TARGETS_KEY,
    queryFn: () => http<Paginated<Target>>("/api/targets/"),
  });
}

export function useCreateTargetMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTargetBody) =>
      http<Target>("/api/targets/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: TARGETS_KEY });
    },
  });
}
