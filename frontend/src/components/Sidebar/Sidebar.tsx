import {
  Bookmark,
  Folder,
  House,
  MessageCircle,
  Plus,
  Search,
  Trash2,
  Workflow,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { BrandMark } from '../Brand/BrandMark'
import type {
  AppPage,
  RecentActivity,
} from '../../types/navigation'

interface SidebarProps {
  activePage: AppPage
  recentActivities: RecentActivity[]
  onNavigate: (page: AppPage) => void
  onNewChat: () => void
  onRecentSelect: (activity: RecentActivity) => void
  onDeleteRecent: (activityId: string) => void
  onClearRecent: () => void
}

interface NavigationItem {
  id: AppPage
  label: string
  icon: LucideIcon
}

const navigationItems: NavigationItem[] = [
  {
    id: 'home',
    label: 'Home',
    icon: House,
  },
  {
    id: 'deep-search',
    label: 'Deep Search',
    icon: Search,
  },
  {
    id: 'projects',
    label: 'Projects',
    icon: Folder,
  },
  {
    id: 'memory',
    label: 'Memory',
    icon: Bookmark,
  },
  {
    id: 'automations',
    label: 'Automations',
    icon: Zap,
  },
  {
    id: 'opspilot',
    label: 'OpsPilot',
    icon: Workflow,
  },
]

function isSameCalendarDay(
  first: Date,
  second: Date,
): boolean {
  return (
    first.getFullYear() === second.getFullYear() &&
    first.getMonth() === second.getMonth() &&
    first.getDate() === second.getDate()
  )
}

function formatRecentTime(createdAt: string): string {
  const date = new Date(createdAt)

  if (Number.isNaN(date.getTime())) {
    return ''
  }

  const now = new Date()

  if (isSameCalendarDay(date, now)) {
    return new Intl.DateTimeFormat(undefined, {
      hour: 'numeric',
      minute: '2-digit',
    }).format(date)
  }

  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)

  if (isSameCalendarDay(date, yesterday)) {
    return 'Yesterday'
  }

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

export function Sidebar({
  activePage,
  recentActivities,
  onNavigate,
  onNewChat,
  onRecentSelect,
  onDeleteRecent,
  onClearRecent,
}: SidebarProps) {
  const visibleRecentActivities =
    recentActivities.slice(0, 6)

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <BrandMark className="brand-mark" size={27} />
        <span>Authentic AI</span>
      </div>

      <button
        className="new-chat-button"
        onClick={onNewChat}
        type="button"
      >
        <Plus size={19} strokeWidth={1.8} />
        <span>New chat</span>
      </button>

      <nav
        aria-label="Primary navigation"
        className="sidebar-navigation"
      >
        {navigationItems.map((item) => {
          const Icon = item.icon
          const isActive = activePage === item.id

          return (
            <button
              className={`navigation-item ${
                isActive ? 'active' : ''
              }`}
              key={item.id}
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              <Icon size={18} strokeWidth={1.75} />
              <span>{item.label}</span>
            </button>
          )
        })}
      </nav>

      <section className="recent-section">
        <div className="sidebar-section-header">
          <p className="sidebar-section-label">Recent</p>

          {recentActivities.length > 0 && (
            <button
              className="recent-clear-button"
              onClick={onClearRecent}
              type="button"
            >
              Clear
            </button>
          )}
        </div>

        {visibleRecentActivities.length === 0 ? (
          <div className="recent-empty">
            <MessageCircle size={15} strokeWidth={1.7} />
            <span>No recent activity yet</span>
          </div>
        ) : (
          <div className="recent-list">
            {visibleRecentActivities.map((activity) => (
              <div
                className="recent-chat-row"
                key={activity.id}
              >
                <button
                  className="recent-chat-main"
                  onClick={() => onRecentSelect(activity)}
                  type="button"
                >
                  <MessageCircle
                    size={13}
                    strokeWidth={1.8}
                  />

                  <span className="recent-chat-title">
                    {activity.title}
                  </span>

                  <time dateTime={activity.updatedAt}>
                    {formatRecentTime(activity.updatedAt)}
                  </time>
                </button>

                <button
                  aria-label={`Delete ${activity.title}`}
                  className="recent-delete-button"
                  onClick={() =>
                    onDeleteRecent(activity.id)
                  }
                  title="Delete history item"
                  type="button"
                >
                  <Trash2 size={13} strokeWidth={1.8} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

    </aside>
  )
}
