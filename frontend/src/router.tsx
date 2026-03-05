import { createBrowserRouter } from 'react-router-dom'
import { lazy, Suspense } from 'react'

const Loading = () => <div className="flex items-center justify-center h-screen text-gray-500">加载中...</div>

// Lazy imports — all pages
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const EtfList = lazy(() => import('@/pages/EtfList'))
const EtfDetail = lazy(() => import('@/pages/EtfDetail'))
const StrategyList = lazy(() => import('@/pages/StrategyList'))
const StrategyDetail = lazy(() => import('@/pages/StrategyDetail'))
const SignalPanel = lazy(() => import('@/pages/SignalPanel'))
const ResearchList = lazy(() => import('@/pages/ResearchList'))
const ResearchDetail = lazy(() => import('@/pages/ResearchDetail'))
const NotFound = lazy(() => import('@/components/common/NotFound'))

// Wrap lazy components with Suspense
function withSuspense(Component: React.LazyExoticComponent<() => JSX.Element>) {
  return (
    <Suspense fallback={<Loading />}>
      <Component />
    </Suspense>
  )
}

// Layout import (non-lazy, used as wrapper)
import Layout from '@/components/common/Layout'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: withSuspense(Dashboard) },
      { path: 'etf', element: withSuspense(EtfList) },
      { path: 'etf/:code', element: withSuspense(EtfDetail) },
      { path: 'strategy', element: withSuspense(StrategyList) },
      { path: 'strategy/:id', element: withSuspense(StrategyDetail) },
      { path: 'signals', element: withSuspense(SignalPanel) },
      { path: 'research', element: withSuspense(ResearchList) },
      { path: 'research/:id', element: withSuspense(ResearchDetail) },
      { path: '*', element: withSuspense(NotFound) },
    ],
  },
])
