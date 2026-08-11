import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type DataLoadErrorProps = {
  isRetrying: boolean;
  onRetry: () => void | Promise<unknown>;
};

export function DataLoadError({
  isRetrying,
  onRetry,
}: DataLoadErrorProps) {
  return (
    <Card role="alert" aria-live="assertive">
      <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <AlertTriangle
            className="mt-0.5 h-5 w-5 shrink-0 text-destructive"
            aria-hidden="true"
          />
          <div>
            <h2 className="font-semibold">データを読み込めませんでした</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              接続または権限を確認して、もう一度お試しください。
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={isRetrying}
          onClick={() => void onRetry()}
        >
          <RotateCw
            className={`mr-2 h-4 w-4 ${isRetrying ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          {isRetrying ? "再試行中..." : "再試行"}
        </Button>
      </CardContent>
    </Card>
  );
}
