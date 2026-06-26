"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { hitlApi } from "@/services/api";
import { useAppStore } from "@/store";
import { useEffect } from "react";
import type { ApprovalResponse } from "@/types";

export function usePendingHitl() {
  const setPendingHitlCount = useAppStore((s) => s.setPendingHitlCount);

  const query = useQuery({
    queryKey: ["hitl", "pending"],
    queryFn: hitlApi.listPending,
    refetchInterval: 4_000,
  });

  useEffect(() => {
    if (query.data) setPendingHitlCount(query.data.count);
  }, [query.data, setPendingHitlCount]);

  return query;
}

export function useAllHitl(limit = 50) {
  return useQuery({
    queryKey: ["hitl", "all", limit],
    queryFn: () => hitlApi.listAll(limit),
    refetchInterval: 8_000,
  });
}

export function useRespondHitl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (resp: ApprovalResponse) => hitlApi.respond(resp),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hitl"] });
    },
  });
}
