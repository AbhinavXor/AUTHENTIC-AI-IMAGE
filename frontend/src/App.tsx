import {
  useEffect,
  useState,
} from 'react'
import { Sidebar } from './components/Sidebar/Sidebar'
import { Navbar } from './components/Navbar/Navbar'
import { Home } from './pages/Home'
import { Memory } from './pages/Memory'
import { UnderDevelopment } from './pages/UnderDevelopment'
import {
  pageTitles,
  type AppPage,
  type RecentActivity,
} from './types/navigation'
import './styles/global.css'

const recentStorageKey =
  'authentic-ai-image.recent-activities.v1'

const sidebarStorageKey =
  'authentic-ai-image.sidebar-open.v1'

const maximumStoredActivities = 100

function loadRecentActivities(): RecentActivity[] {
  try {
    const storedValue =
      window.localStorage.getItem(recentStorageKey)

    if (!storedValue) {
      return []
    }

    const parsedValue: unknown = JSON.parse(storedValue)

    if (!Array.isArray(parsedValue)) {
      return []
    }

    return parsedValue
      .filter(
        (item): item is RecentActivity =>
          typeof item === 'object' &&
          item !== null &&
          'id' in item &&
          'title' in item &&
          'createdAt' in item &&
          typeof item.id === 'string' &&
          typeof item.title === 'string' &&
          typeof item.createdAt === 'string',
      )
      .slice(0, maximumStoredActivities)
  } catch {
    return []
  }
}

function loadSidebarState(): boolean {
  try {
    return (
      window.localStorage.getItem(sidebarStorageKey) !==
      'closed'
    )
  } catch {
    return true
  }
}

function createActivityId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID()
  }

  return `${Date.now()}-${Math.random()
    .toString(16)
    .slice(2)}`
}

function App() {
  const [activePage, setActivePage] =
    useState<AppPage>('home')

  const [homeSession, setHomeSession] = useState(0)

  const [isSidebarOpen, setIsSidebarOpen] =
    useState(loadSidebarState)

  const [recentActivities, setRecentActivities] =
    useState<RecentActivity[]>(loadRecentActivities)

  useEffect(() => {
    window.localStorage.setItem(
      recentStorageKey,
      JSON.stringify(recentActivities),
    )
  }, [recentActivities])

  useEffect(() => {
    window.localStorage.setItem(
      sidebarStorageKey,
      isSidebarOpen ? 'open' : 'closed',
    )
  }, [isSidebarOpen])

  const handleNavigate = (page: AppPage) => {
    setActivePage(page)

    if (window.innerWidth <= 820) {
      setIsSidebarOpen(false)
    }
  }

  const handleNewChat = () => {
    setActivePage('home')
    setHomeSession((current) => current + 1)

    if (window.innerWidth <= 820) {
      setIsSidebarOpen(false)
    }
  }

  const handleActivityCreated = (title: string) => {
    const newActivity: RecentActivity = {
      id: createActivityId(),
      title,
      createdAt: new Date().toISOString(),
    }

    setRecentActivities((currentActivities) =>
      [
        newActivity,
        ...currentActivities.filter(
          (activity) => activity.title !== title,
        ),
      ].slice(0, maximumStoredActivities),
    )
  }

  const handleDeleteActivity = (
    activityId: string,
  ) => {
    setRecentActivities((currentActivities) =>
      currentActivities.filter(
        (activity) => activity.id !== activityId,
      ),
    )
  }

  const handleClearHistory = () => {
    const shouldClear = window.confirm(
      'Delete all saved history? This action cannot be undone.',
    )

    if (shouldClear) {
      setRecentActivities([])
    }
  }

  const renderCurrentPage = () => {
    if (activePage === 'home') {
      return (
        <Home
          key={homeSession}
          onActivityCreated={handleActivityCreated}
          onOpenDevelopment={handleNavigate}
        />
      )
    }

    if (activePage === 'memory') {
      return (
        <Memory
          activities={recentActivities}
          onClearHistory={handleClearHistory}
          onDeleteActivity={handleDeleteActivity}
        />
      )
    }

    return (
      <UnderDevelopment
        onBack={() => handleNavigate('home')}
        title={pageTitles[activePage]}
      />
    )
  }

  return (
    <div
      className={`app-shell ${
        isSidebarOpen
          ? 'sidebar-open'
          : 'sidebar-collapsed'
      }`}
    >
      <Sidebar
        activePage={activePage}
        onClearRecent={handleClearHistory}
        onDeleteRecent={handleDeleteActivity}
        onNavigate={handleNavigate}
        onNewChat={handleNewChat}
        onRecentSelect={() => handleNavigate('memory')}
        recentActivities={recentActivities}
      />

      <div className="main-shell">
        <Navbar
          isSidebarOpen={isSidebarOpen}
          onNavigate={handleNavigate}
          onToggleSidebar={() =>
            setIsSidebarOpen((current) => !current)
          }
        />

        <main className="main-content">
          {renderCurrentPage()}
        </main>
      </div>
    </div>
  )
}

export default App
