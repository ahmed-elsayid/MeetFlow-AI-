"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "react-hot-toast";
import { queryClient } from "@/lib/query-client";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#1E1E2A",
            color: "#E2E8F0",
            border: "1px solid #2A2A3A",
            borderRadius: "10px",
            fontSize: "13px",
          },
          success: {
            iconTheme: { primary: "#10B981", secondary: "#1E1E2A" },
          },
          error: {
            iconTheme: { primary: "#EF4444", secondary: "#1E1E2A" },
          },
        }}
      />
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}
