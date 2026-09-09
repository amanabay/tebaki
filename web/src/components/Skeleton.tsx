import { cn } from "cn";

/** Archival paper shimmer loading block. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("skeleton h-4 w-full", className)} />;
}
