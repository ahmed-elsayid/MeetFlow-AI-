import { cn } from "@/lib/utils";

type Variant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "accent"
  | "primary"
  | "dim";

interface BadgeProps {
  children: React.ReactNode;
  variant?: Variant;
  size?: "sm" | "md";
  className?: string;
  dot?: boolean;
}

const variants: Record<Variant, string> = {
  default: "bg-bg-elevated text-text-muted border-border",
  success: "bg-success-muted text-success-light border-success/30",
  warning: "bg-warning-muted text-warning-light border-warning/30",
  danger: "bg-danger-muted text-danger-light border-danger/30",
  accent: "bg-accent-muted text-accent border-accent/30",
  primary: "bg-primary-muted text-primary-light border-primary/30",
  dim: "bg-bg-elevated text-text-dim border-border/50",
};

const dotColors: Record<Variant, string> = {
  default: "bg-text-muted",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  accent: "bg-accent",
  primary: "bg-primary",
  dim: "bg-text-dim",
};

export default function Badge({
  children,
  variant = "default",
  size = "sm",
  className,
  dot = false,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border rounded-full font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        variants[variant],
        className
      )}
    >
      {dot && (
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full shrink-0",
            dotColors[variant]
          )}
        />
      )}
      {children}
    </span>
  );
}
