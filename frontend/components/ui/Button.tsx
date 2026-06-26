import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success" | "accent";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: React.ReactNode;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-primary hover:bg-primary-hover text-white border-transparent shadow-lg shadow-primary/20",
  secondary:
    "bg-bg-elevated hover:bg-bg-overlay text-text border-border hover:border-border-strong",
  ghost:
    "bg-transparent hover:bg-bg-elevated text-text-muted hover:text-text border-transparent",
  danger:
    "bg-danger/10 hover:bg-danger/20 text-danger-light border-danger/30",
  success:
    "bg-success/10 hover:bg-success/20 text-success-light border-success/30",
  accent:
    "bg-accent/10 hover:bg-accent/20 text-accent border-accent/30",
};

const sizes: Record<Size, string> = {
  sm: "h-7 px-3 text-xs gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
  lg: "h-11 px-6 text-base gap-2",
};

export default function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center rounded-lg border font-medium",
        "transition-all duration-150 cursor-pointer",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className
      )}
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin shrink-0" />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}
