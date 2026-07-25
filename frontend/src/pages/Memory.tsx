import {
  Clock3,
  Database,
  Search,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import type { RecentActivity } from '../types/navigation'

interface MemoryProps {
  activities: RecentActivity[]
  onDeleteActivity: (activityId: string) => void
  onClearHistory: () => void
}

function formatDateTime(createdAt: string): string {
  const date = new Date(createdAt)

  if (Number.isNaN(date.getTime())) {
    return 'Unknown time'
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function Memory({
  activities,
  onDeleteActivity,
  onClearHistory,
}: MemoryProps) {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredActivities = useMemo(() => {
    const normalizedQuery =
      searchQuery.trim().toLowerCase()

    if (!normalizedQuery) {
      return activities
    }

    return activities.filter((activity) =>
      activity.title
        .toLowerCase()
        .includes(normalizedQuery),
    )
  }, [activities, searchQuery])

  return (
    <div className="memory-page">
      <section className="memory-container">
        <header className="memory-header">
          <div className="memory-heading">
            <div className="memory-heading-icon">
              <Database size={23} strokeWidth={1.7} />
            </div>

            <div>
              <p>Authentic AI</p>
              <h1>Memory</h1>
              <span>
                Your complete verification and prompt history.
              </span>
            </div>
          </div>

          {activities.length > 0 && (
            <button
              className="memory-clear-button"
              onClick={onClearHistory}
              type="button"
            >
              <Trash2 size={16} />
              <span>Clear history</span>
            </button>
          )}
        </header>

        <div className="memory-summary">
          <div>
            <ShieldCheck size={18} strokeWidth={1.8} />

            <span>
              <strong>{activities.length}</strong>
              saved activities
            </span>
          </div>

          <p>
            History is currently stored locally in this browser.
          </p>
        </div>

        <div className="memory-search">
          <Search size={18} strokeWidth={1.8} />

          <input
            aria-label="Search memory"
            onChange={(event) =>
              setSearchQuery(event.target.value)
            }
            placeholder="Search your history"
            type="search"
            value={searchQuery}
          />
        </div>

        {activities.length === 0 ? (
          <div className="memory-empty-state">
            <div>
              <Clock3 size={27} strokeWidth={1.6} />
            </div>

            <h2>No history yet</h2>

            <p>
              Your submitted prompts and verification activities
              will appear here automatically.
            </p>
          </div>
        ) : filteredActivities.length === 0 ? (
          <div className="memory-empty-state compact">
            <div>
              <Search size={24} strokeWidth={1.6} />
            </div>

            <h2>No matching history</h2>

            <p>
              Try searching with a different word or phrase.
            </p>
          </div>
        ) : (
          <div className="memory-list">
            {filteredActivities.map((activity) => (
              <article
                className="memory-history-item"
                key={activity.id}
              >
                <div className="memory-history-icon">
                  <Clock3 size={18} strokeWidth={1.7} />
                </div>

                <div className="memory-history-content">
                  <strong>{activity.title}</strong>

                  <time dateTime={activity.updatedAt}>
                    {formatDateTime(activity.updatedAt)}
                  </time>
                </div>

                <button
                  aria-label={`Delete ${activity.title}`}
                  className="memory-delete-button"
                  onClick={() =>
                    onDeleteActivity(activity.id)
                  }
                  title="Delete history item"
                  type="button"
                >
                  <Trash2 size={16} strokeWidth={1.8} />
                </button>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
