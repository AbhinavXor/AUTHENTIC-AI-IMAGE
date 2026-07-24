export type AppPage =
  | 'home'
  | 'deep-search'
  | 'projects'
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

export interface RecentActivity {
  id: string
  title: string
  createdAt: string
}

export const pageTitles: Record<AppPage, string> = {
  home: 'Home',
  'deep-search': 'Deep Search',
  projects: 'Projects',
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
