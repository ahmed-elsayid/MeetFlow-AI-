"use client";

import { useQuery } from "@tanstack/react-query";
import { auditApi } from "@/services/api";

export function useAuditEvents(meetingId?: string, limit = 100) {
  return useQuery({
    queryKey: ["audit", "events", meetingId, limit],
    queryFn: () => auditApi.getEvents(meetingId, limit),
    refetchInterval: 10_000,
  });
}
