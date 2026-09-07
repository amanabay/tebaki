import { cn } from "cn";
import { statusInfo } from "@/lib/strings";

export function StatusStamp({ status, animate = false }: { status: string; animate?: boolean }) {
  const info = statusInfo(status);
  return (
    <span
      className={cn(
        "stamp text-[10px]",
        info.className,
        animate && "stamp-animate",
      )}
    >
      {info.label}
    </span>
  );
}
