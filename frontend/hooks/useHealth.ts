"use client";

import { useQuery } from "@tanstack/react-query";
import { healthApi } from "@/services/api";
import { useAppStore } from "@/store";
import { useEffect } from "react";

export function useHealth() {
  const setHealth = useAppStore((s) => s.setHealth);

  const query = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.check,
    refetchInterval: 15_000,
  });

  useEffect(() => {
    if (query.data) setHealth(query.data);
  }, [query.data, setHealth]);

  return query;
}
