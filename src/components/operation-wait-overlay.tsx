import { LoaderCircle } from "lucide-react";
import { createPortal } from "react-dom";

import { OPERATION_WAIT_OVERLAY_LAYER_CLASS } from "@/components/operation-wait-overlay-constants";
import { cn } from "@/lib/utils";

type OperationWaitOverlayProps = {
  open: boolean;
  title: string;
  description?: string;
  className?: string;
};

export function OperationWaitOverlay({
  open,
  title,
  description,
  className,
}: OperationWaitOverlayProps) {
  if (!open) return null;

  const overlay = (
    <div
      className={cn(OPERATION_WAIT_OVERLAY_LAYER_CLASS, className)}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="flex w-full max-w-sm flex-col items-center gap-3 rounded-lg border bg-background p-5 text-center shadow-lg">
        <LoaderCircle className="h-8 w-8 animate-spin text-primary" />
        <div className="space-y-1">
          <p className="text-sm font-semibold">{title}</p>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return overlay;

  return createPortal(overlay, document.body);
}
