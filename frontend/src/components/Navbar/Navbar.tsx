import {
  Bell,
  ChevronDown,
  History,
  Menu,
  Search,
} from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
} from 'react'

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
  const launchTimerRef = useRef<number | null>(null)
  const [isSherryLaunching, setIsSherryLaunching] =
    useState(false)

  useEffect(() => {
    return () => {
      if (launchTimerRef.current !== null) {
        window.clearTimeout(launchTimerRef.current)
      }
    }
  }, [])

  const handleSherryLaunch = () => {
    if (isSherryLaunching) {
      return
    }

    setIsSherryLaunching(true)

    if (launchTimerRef.current !== null) {
      window.clearTimeout(launchTimerRef.current)
    }

    launchTimerRef.current = window.setTimeout(
      () => {
        launchTimerRef.current = null
        setIsSherryLaunching(false)
        onNavigate('sherry')
      },
      220,
    )
  }

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

        <div className="navbar-sherry-wrap">
          <button
            aria-label="Open Sherry voice assistant"
            aria-pressed={isSherryLaunching}
            className={[
              'sherry-navbar-button',
              isSherryLaunching ? 'is-launching' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            disabled={isSherryLaunching}
            onClick={handleSherryLaunch}
            title="Sherry voice assistant"
            type="button"
          >
            <SherryMark size={32} />
          </button>

          {isSherryLaunching && (
            <div
              aria-live="polite"
              className="navbar-sherry-launch-pill"
              role="status"
            >
              <span
                aria-hidden="true"
                className="inline-progress-dots"
              >
                <i />
                <i />
                <i />
              </span>
              <span>Opening Sherry…</span>
            </div>
          )}
        </div>

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
