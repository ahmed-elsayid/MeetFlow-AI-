import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  elevated?: boolean;
  onClick?: () => void;
  hover?: boolean;
}

export default function Card({
  children,
  className,
  elevated = false,
  onClick,
  hover = false,
}: CardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "rounded-xl border",
        elevated ? "bg-bg-elevated border-border" : "bg-bg-surface border-border",
        (hover || onClick) &&
          "cursor-pointer hover:border-border-strong hover:bg-bg-elevated transition-colors duration-150",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("px-5 py-4 border-b border-border", className)}>
      {children}
    </div>
  );
}

export function CardBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("px-5 py-4", className)}>{children}</div>;
}

export function CardFooter({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "px-5 py-3 border-t border-border bg-bg-base/30 rounded-b-xl",
        className
      )}
    >
      {children}
    </div>
  );
}
