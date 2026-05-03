import { createBrowserRouter, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import Layout from "@/pages/_layout";

const NotFoundPage = lazy(() => import("@/pages/not-found"));
const DashboardPage = lazy(() => import("@/pages/dashboard"));
const ApplicationsPage = lazy(() => import("@/pages/applications"));
const QueuePage = lazy(() => import("@/pages/queue"));
const ApplicationDetailPage = lazy(() => import("@/pages/application-detail"));
const MentionsPage = lazy(() => import("@/pages/mentions"));
const ResourcesPage = lazy(() => import("@/pages/resources"));
const MastersPage = lazy(() => import("@/pages/masters"));

// ローディングコンポーネント
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-[400px]">
    <div className="flex flex-col items-center gap-2">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
      <p className="text-sm text-muted-foreground">読み込み中...</p>
    </div>
  </div>
);

// Suspenseラッパー
const withSuspense = (
  Component: React.LazyExoticComponent<() => React.JSX.Element>,
) => (
  <Suspense fallback={<PageLoader />}>
    <Component />
  </Suspense>
);

// IMPORTANT: Do not remove or modify the code below!
// Normalize basename when hosted in Power Apps
const BASENAME = new URL(".", location.href).pathname;
if (location.pathname.endsWith("/index.html")) {
  history.replaceState(null, "", BASENAME + location.search + location.hash);
}

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <Layout showHeader={true} />,
      errorElement: withSuspense(NotFoundPage),
      children: [
        { index: true, element: <Navigate to="/dashboard" replace /> },
        { path: "dashboard", element: withSuspense(DashboardPage) },
        { path: "applications", element: withSuspense(ApplicationsPage) },
        {
          path: "applications/:id",
          element: withSuspense(ApplicationDetailPage),
        },
        { path: "queue", element: withSuspense(QueuePage) },
        { path: "mentions", element: withSuspense(MentionsPage) },
        { path: "resources", element: withSuspense(ResourcesPage) },
        { path: "masters", element: withSuspense(MastersPage) },
      ],
    },
  ],
  {
    basename: BASENAME, // IMPORTANT: Set basename for proper routing when hosted in Power Apps
  },
);
