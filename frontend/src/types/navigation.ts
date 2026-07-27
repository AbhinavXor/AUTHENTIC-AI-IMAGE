import type {
  ConversationRecord,
} from './chat'

export type AppPage =
  | 'home'
  | 'deep-search'
  | 'projects'
  | 'artifact-studio'
  | 'memory'
  | 'automations'
  | 'opspilot'
  | 'search'
  | 'sherry'
  | 'history'
  | 'notifications'
  | 'profile'
  | 'model-selector'
  | 'opspilot-runtime'

export type RecentActivity =
  ConversationRecord

export const pageTitles: Record<AppPage, string> = {
  home: 'Home',
  'deep-search': 'Deep Search',
  projects: 'Projects',
  'artifact-studio': 'Artifact Studio',
  memory: 'Memory',
  automations: 'Automations',
  opspilot: 'OpsPilot',
  search: 'Search',
  sherry: 'Sherry',
  history: 'History',
  notifications: 'Notifications',
  profile: 'Profile',
  'model-selector': 'Serenya Model Selector',
  'opspilot-runtime': 'OpsPilot Runtime',
}
