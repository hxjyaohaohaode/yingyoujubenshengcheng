import { Suspense, lazy, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import AppLayout from './components/Layout'
import PageTransition from './components/PageTransition'
import ErrorBoundary from './components/ErrorBoundary'
import GlobalLoading from './components/GlobalLoading'
import { useProjectStore } from './stores/projectStore'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const WorldSettings = lazy(() => import('./pages/WorldSettings'))
const Characters = lazy(() => import('./pages/Characters'))
const Foreshadows = lazy(() => import('./pages/Foreshadows'))
const ChapterOutline = lazy(() => import('./pages/ChapterOutline'))
const SceneWorkshop = lazy(() => import('./pages/SceneWorkshop'))
const ReviewPanel = lazy(() => import('./pages/ReviewPanel'))
const EmotionCurve = lazy(() => import('./pages/EmotionCurve'))
const Export = lazy(() => import('./pages/Export'))
const Settings = lazy(() => import('./pages/Settings'))
const PipelineView = lazy(() => import('./pages/PipelineView'))
const ScriptViz = lazy(() => import('./pages/ScriptViz'))
const ScriptPreview = lazy(() => import('./pages/ScriptPreview'))

function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route
          path="/"
          element={
            <Suspense fallback={<GlobalLoading pageType="dashboard" />}>
              <Dashboard />
            </Suspense>
          }
        />
        <Route
          path="/world"
          element={
            <Suspense fallback={<GlobalLoading pageType="world" />}>
              <WorldSettings />
            </Suspense>
          }
        />
        <Route
          path="/characters"
          element={
            <Suspense fallback={<GlobalLoading pageType="characters" />}>
              <Characters />
            </Suspense>
          }
        />
        <Route
          path="/foreshadows"
          element={
            <Suspense fallback={<GlobalLoading pageType="foreshadows" />}>
              <Foreshadows />
            </Suspense>
          }
        />
        <Route
          path="/chapters"
          element={
            <Suspense fallback={<GlobalLoading pageType="chapters" />}>
              <ChapterOutline />
            </Suspense>
          }
        />
        <Route
          path="/scenes"
          element={
            <Suspense fallback={<GlobalLoading pageType="scenes" />}>
              <SceneWorkshop />
            </Suspense>
          }
        />
        <Route
          path="/review"
          element={
            <Suspense fallback={<GlobalLoading pageType="review" />}>
              <ReviewPanel />
            </Suspense>
          }
        />
        <Route
          path="/emotion-curve"
          element={
            <Suspense fallback={<GlobalLoading pageType="emotion-curve" />}>
              <EmotionCurve />
            </Suspense>
          }
        />
        <Route
          path="/export"
          element={
            <Suspense fallback={<GlobalLoading pageType="export" />}>
              <Export />
            </Suspense>
          }
        />
        <Route
          path="/settings"
          element={
            <Suspense fallback={<GlobalLoading pageType="settings" />}>
              <Settings />
            </Suspense>
          }
        />
        <Route
          path="/pipeline"
          element={
            <Suspense fallback={<GlobalLoading pageType="pipeline" />}>
              <PipelineView />
            </Suspense>
          }
        />
        <Route
          path="/script-viz"
          element={
            <Suspense fallback={<GlobalLoading pageType="script-viz" />}>
              <ScriptViz />
            </Suspense>
          }
        />
        <Route
          path="/script-preview"
          element={
            <Suspense fallback={<GlobalLoading pageType="script-preview" />}>
              <ScriptPreview />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  )
}

function App() {
  const { unsavedChanges } = useProjectStore()

  useEffect(() => {
    if (!unsavedChanges) return

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }

    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [unsavedChanges])

  return (
    <ErrorBoundary>
      <PageTransition>
        <AppRoutes />
      </PageTransition>
    </ErrorBoundary>
  )
}

export default App
