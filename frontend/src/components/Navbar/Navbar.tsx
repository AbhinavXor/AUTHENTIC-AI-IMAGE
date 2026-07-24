import {
  Bell,
  ChevronDown,
  History,
  Menu,
  Search,
} from 'lucide-react'
import { SherryMark } from '../Brand/SherryMark'
import type { AppPage } from '../../types/navigation'

interface NavbarProps {
  isSidebarOpen: boolean
  onNavigate: (page: AppPage) => void
  onToggleSidebar: () => void
}

export function Navbar({
  isSidebarOpen,
  onNavigate,
  onToggleSidebar,
}: NavbarProps) {
  return (
    <header className="top-navbar">
      <div className="navbar-left">
        <button
          aria-expanded={isSidebarOpen}
          aria-label={
            isSidebarOpen ? 'Hide sidebar' : 'Show sidebar'
          }
          className="sidebar-toggle-button"
          onClick={onToggleSidebar}
          title={isSidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
          type="button"
        >
          <Menu size={21} strokeWidth={1.8} />
        </button>

        <button
          aria-label="Open Serenya model selector"
          className="model-selector"
          onClick={() => onNavigate('model-selector')}
          title="Serenya model"
          type="button"
        >
          <span>Serenya</span>
          <ChevronDown size={15} strokeWidth={1.8} />
        </button>
      </div>

      <div className="navbar-actions">
        <button
          aria-label="Search"
          className="navbar-search navbar-action-button"
          onClick={() => onNavigate('search')}
          title="Search"
          type="button"
        >
          <Search size={18} strokeWidth={1.8} />
          <span>Search</span>
        </button>

        <button
          aria-label="Open Sherry voice assistant"
          className="sherry-navbar-button"
          onClick={() => onNavigate('sherry')}
          title="Sherry voice assistant"
          type="button"
        >
          <SherryMark size={32} />
        </button>

        <button
          aria-label="History"
          className="navbar-icon navbar-action-button"
          onClick={() => onNavigate('history')}
          title="History"
          type="button"
        >
          <History size={20} strokeWidth={1.75} />
        </button>

        <button
          aria-label="Notifications"
          className="navbar-icon navbar-action-button"
          onClick={() => onNavigate('notifications')}
          title="Notifications"
          type="button"
        >
          <Bell size={20} strokeWidth={1.75} />
        </button>

        <button
          aria-label="Private profile"
          className="profile-avatar profile-button"
          onClick={() => onNavigate('profile')}
          title="Private profile"
          type="button"
        >
          S
        </button>
      </div>
    </header>
  )
}
