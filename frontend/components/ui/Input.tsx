import { cn } from "@/lib/utils";
import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: React.ReactNode;
}

export default function Input({
  label,
  error,
  hint,
  icon,
  className,
  ...props
}: InputProps) {
  return (
    <div className="flex flex-col gap-1.5 w-full">
      {label && (
        <label className="text-sm font-medium text-text-muted">{label}</label>
      )}
      <div className="relative">
        {icon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim">
            {icon}
          </span>
        )}
        <input
          {...props}
          className={cn(
            "w-full h-9 px-3 text-sm rounded-lg border",
            "bg-bg-elevated border-border text-text placeholder:text-text-dim",
            "focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "transition-colors duration-150",
            icon && "pl-9",
            error && "border-danger focus:border-danger focus:ring-danger/30",
            className
          )}
        />
      </div>
      {error && <p className="text-xs text-danger-light">{error}</p>}
      {hint && !error && <p className="text-xs text-text-dim">{hint}</p>}
    </div>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Textarea({ label, error, hint, className, ...props }: TextareaProps) {
  return (
    <div className="flex flex-col gap-1.5 w-full">
      {label && (
        <label className="text-sm font-medium text-text-muted">{label}</label>
      )}
      <textarea
        {...props}
        className={cn(
          "w-full px-3 py-2 text-sm rounded-lg border min-h-[80px] resize-y",
          "bg-bg-elevated border-border text-text placeholder:text-text-dim",
          "focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30",
          "disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150",
          error && "border-danger",
          className
        )}
      />
      {error && <p className="text-xs text-danger-light">{error}</p>}
      {hint && !error && <p className="text-xs text-text-dim">{hint}</p>}
    </div>
  );
}
