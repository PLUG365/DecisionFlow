import { useEffect } from "react"
import { getContext } from "@microsoft/power-apps/app"
import { PowerProvider } from "./providers/power-provider"
import { ThemeProvider } from "@/providers/theme-provider"
import { SonnerProvider } from "@/providers/sonner-provider"
import { QueryProvider } from "./providers/query-provider"
import { RouterProvider } from "react-router-dom"
import { router } from "@/router"

export default function App() {
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const context = await getContext();
        if (cancelled) return;
        const deepLink = context.app.queryParams?.deepLink;
        if (deepLink && /^\/[A-Za-z][A-Za-z0-9/-]*$/.test(deepLink)) {
          router.navigate(deepLink, { replace: true });
        }
      } catch {
        // SDK 未初期化や非 Power Apps 環境ではフォールバックで location.search を試す
        const params = new URLSearchParams(location.search);
        const deepLink = params.get("deepLink");
        if (deepLink && /^\/[A-Za-z][A-Za-z0-9/-]*$/.test(deepLink)) {
          router.navigate(deepLink, { replace: true });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PowerProvider>
      <ThemeProvider>
        <SonnerProvider>
          <QueryProvider>
            <RouterProvider router={router} />
          </QueryProvider>
        </SonnerProvider>
      </ThemeProvider>
    </PowerProvider>
  )
}