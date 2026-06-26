"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { botApi } from "@/services/api";
import type { BotStartRequest } from "@/types";

export function useBotStatus(meetingId: string, enabled = true) {
  return useQuery({
    queryKey: ["bot", meetingId, "status"],
    queryFn: () => botApi.getStatus(meetingId),
    enabled: enabled && !!meetingId,
    refetchInterval: 3_000,
  });
}

export function useStartBot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: BotStartRequest) => botApi.start(req),
    onSuccess: (_data, req) => {
      qc.invalidateQueries({ queryKey: ["bot", req.meeting_id] });
    },
  });
}

export function useStopBot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (meetingId: string) => botApi.stop(meetingId),
    onSuccess: (_data, meetingId) => {
      qc.invalidateQueries({ queryKey: ["bot", meetingId] });
    },
  });
}
