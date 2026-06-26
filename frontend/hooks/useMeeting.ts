"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { meetingApi } from "@/services/api";
import { useAppStore } from "@/store";
import type { ChunkInput, EndMeetingRequest, MeetingStartRequest } from "@/types";

export function useMeetingStatus(meetingId: string, enabled = true) {
  return useQuery({
    queryKey: ["meeting", meetingId, "status"],
    queryFn: () => meetingApi.getStatus(meetingId),
    enabled: enabled && !!meetingId,
    refetchInterval: 4_000,
  });
}

export function useStartMeeting() {
  const addMeeting = useAppStore((s) => s.addMeeting);

  return useMutation({
    mutationFn: (req: MeetingStartRequest) => meetingApi.start(req),
    onSuccess: (data, req) => {
      addMeeting({
        meeting_id: data.meeting_id,
        title: req.title || data.meeting_id,
        participants: req.participants || [],
        started_at: new Date().toISOString(),
        status: null,
      });
    },
  });
}

export function useSendChunk() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (chunk: ChunkInput) => meetingApi.sendChunk(chunk),
    onSuccess: (_data, chunk) => {
      qc.invalidateQueries({ queryKey: ["meeting", chunk.meeting_id] });
    },
  });
}

export function useEndMeeting() {
  const qc = useQueryClient();
  const updateMeetingStatus = useAppStore((s) => s.updateMeetingStatus);

  return useMutation({
    mutationFn: ({
      meetingId,
      req,
    }: {
      meetingId: string;
      req: EndMeetingRequest;
    }) => meetingApi.end(meetingId, req),
    onSuccess: (_data, { meetingId }) => {
      qc.invalidateQueries({ queryKey: ["meeting", meetingId] });
      updateMeetingStatus(meetingId, {
        status: {
          status: "ended",
          chunks_processed: 0,
          notes_sections: 0,
          tasks_extracted: 0,
          research_briefs: 0,
          pending_approvals: 0,
          errors: 0,
        },
      });
    },
  });
}

export function useUploadTranscript() {
  const addMeeting = useAppStore((s) => s.addMeeting);

  return useMutation({
    mutationFn: (formData: FormData) => meetingApi.uploadTranscript(formData),
    onSuccess: (data, formData) => {
      addMeeting({
        meeting_id: data.meeting_id,
        title: (formData.get("title") as string) || data.meeting_id,
        participants: [],
        started_at: new Date().toISOString(),
        status: null,
      });
    },
  });
}

export function useDeleteMeeting() {
  const qc = useQueryClient();
  const removeMeeting = useAppStore((s) => s.removeMeeting);

  return useMutation({
    mutationFn: (meetingId: string) => meetingApi.delete(meetingId),
    onSuccess: (_data, meetingId) => {
      removeMeeting(meetingId);
      qc.removeQueries({ queryKey: ["meeting", meetingId] });
    },
  });
}
