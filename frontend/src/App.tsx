import {
  useEffect,
  useMemo,
  useState,
} from 'react'
import { Sidebar } from './components/Sidebar/Sidebar'
import { Navbar } from './components/Navbar/Navbar'
import { Home } from './pages/Home'
import { Memory } from './pages/Memory'
import { UnderDevelopment } from './pages/UnderDevelopment'
import type {
  ConversationMessage,
  ConversationRecord,
} from './types/chat'
import {
  pageTitles,
  type AppPage,
} from './types/navigation'
import './styles/global.css'

const conversationStorageKey =
  'authentic-ai-image.conversations.v2'

const sidebarStorageKey =
  'authentic-ai-image.sidebar-open.v1'

const maximumStoredConversations = 100

function isConversationMessage(
  value: unknown,
): value is ConversationMessage {
  if (
    typeof value !== 'object' ||
    value === null
  ) {
    return false
  }

  const message =
    value as Record<string, unknown>

  return (
    typeof message.id === 'string' &&
    (
      message.role === 'user' ||
      message.role === 'assistant'
    ) &&
    typeof message.content === 'string'
  )
}

function isConversationRecord(
  value: unknown,
): value is ConversationRecord {
  if (
    typeof value !== 'object' ||
    value === null
  ) {
    return false
  }

  const conversation =
    value as Record<string, unknown>

  return (
    typeof conversation.id === 'string' &&
    typeof conversation.title === 'string' &&
    typeof conversation.createdAt === 'string' &&
    typeof conversation.updatedAt === 'string' &&
    Array.isArray(conversation.messages) &&
    conversation.messages.every(
      isConversationMessage,
    )
  )
}

function loadConversations():
  ConversationRecord[] {
  try {
    const stored =
      window.localStorage.getItem(
        conversationStorageKey,
      )

    if (!stored) {
      return []
    }

    const parsed: unknown =
      JSON.parse(stored)

    if (!Array.isArray(parsed)) {
      return []
    }

    return parsed
      .filter(isConversationRecord)
      .sort(
        (first, second) =>
          new Date(second.updatedAt).getTime() -
          new Date(first.updatedAt).getTime(),
      )
      .slice(
        0,
        maximumStoredConversations,
      )
  } catch {
    return []
  }
}

function loadSidebarState(): boolean {
  try {
    return (
      window.localStorage.getItem(
        sidebarStorageKey,
      ) !== 'closed'
    )
  } catch {
    return true
  }
}

function App() {
  const [activePage, setActivePage] =
    useState<AppPage>('home')

  const [isSidebarOpen, setIsSidebarOpen] =
    useState(loadSidebarState)

  const [conversations, setConversations] =
    useState<ConversationRecord[]>(
      loadConversations,
    )

  const [
    selectedConversationId,
    setSelectedConversationId,
  ] = useState<string | null>(null)

  const [homeVersion, setHomeVersion] =
    useState(0)

  const selectedConversation = useMemo(
    () =>
      conversations.find(
        (conversation) =>
          conversation.id ===
          selectedConversationId,
      ) ?? null,
    [
      conversations,
      selectedConversationId,
    ],
  )

  useEffect(() => {
    window.localStorage.setItem(
      conversationStorageKey,
      JSON.stringify(conversations),
    )
  }, [conversations])

  useEffect(() => {
    window.localStorage.setItem(
      sidebarStorageKey,
      isSidebarOpen ? 'open' : 'closed',
    )
  }, [isSidebarOpen])

  const handleNavigate = (
    page: AppPage,
  ) => {
    setActivePage(page)

    if (window.innerWidth <= 820) {
      setIsSidebarOpen(false)
    }
  }

  const handleNewChat = () => {
    setActivePage('home')
    setSelectedConversationId(null)
    setHomeVersion(
      (current) => current + 1,
    )

    if (window.innerWidth <= 820) {
      setIsSidebarOpen(false)
    }
  }

  const handleConversationUpdated = (
    conversation: ConversationRecord,
  ) => {
    setConversations((current) =>
      [
        conversation,
        ...current.filter(
          (item) =>
            item.id !== conversation.id,
        ),
      ]
        .sort(
          (first, second) =>
            new Date(
              second.updatedAt,
            ).getTime() -
            new Date(
              first.updatedAt,
            ).getTime(),
        )
        .slice(
          0,
          maximumStoredConversations,
        ),
    )

    setSelectedConversationId(
      conversation.id,
    )
  }

  const handleRecentSelect = (
    conversation: ConversationRecord,
  ) => {
    setSelectedConversationId(
      conversation.id,
    )

    setActivePage('home')

    setHomeVersion(
      (current) => current + 1,
    )

    if (window.innerWidth <= 820) {
      setIsSidebarOpen(false)
    }
  }

  const handleDeleteConversation = (
    conversationId: string,
  ) => {
    setConversations((current) =>
      current.filter(
        (conversation) =>
          conversation.id !==
          conversationId,
      ),
    )

    if (
      selectedConversationId ===
      conversationId
    ) {
      setSelectedConversationId(null)
      setHomeVersion(
        (current) => current + 1,
      )
    }
  }

  const handleClearHistory = () => {
    const shouldClear = window.confirm(
      'Delete all saved conversations? This action cannot be undone.',
    )

    if (!shouldClear) {
      return
    }

    setConversations([])
    setSelectedConversationId(null)
    setHomeVersion(
      (current) => current + 1,
    )
  }

  const renderCurrentPage = () => {
    if (activePage === 'home') {
      return (
        <Home
          initialConversation={
            selectedConversation
          }
          key={`${homeVersion}:${
            selectedConversation?.id ??
            'new'
          }`}
          onConversationUpdated={
            handleConversationUpdated
          }
          onOpenDevelopment={
            handleNavigate
          }
        />
      )
    }

    if (activePage === 'memory') {
      return (
        <Memory
          activities={conversations}
          onClearHistory={
            handleClearHistory
          }
          onDeleteActivity={
            handleDeleteConversation
          }
        />
      )
    }

    return (
      <UnderDevelopment
        onBack={() =>
          handleNavigate('home')
        }
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
        onClearRecent={
          handleClearHistory
        }
        onDeleteRecent={
          handleDeleteConversation
        }
        onNavigate={handleNavigate}
        onNewChat={handleNewChat}
        onRecentSelect={
          handleRecentSelect
        }
        recentActivities={
          conversations
        }
      />

      <div className="main-shell">
        <Navbar
          isSidebarOpen={
            isSidebarOpen
          }
          onNavigate={handleNavigate}
          onToggleSidebar={() =>
            setIsSidebarOpen(
              (current) => !current,
            )
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
