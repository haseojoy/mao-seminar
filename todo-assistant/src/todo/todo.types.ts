export type Priority = 'high' | 'medium' | 'low';
export type ReplyUrgency = 'red' | 'yellow' | 'green';

export interface TodoItem {
  title: string;
  priority: Priority;
  source: 'Gmail' | 'Slack';
  sender: string;
  date: string;
  deadline?: string;
  project?: string;
}

export interface ReplyItem {
  subject: string;
  sender: string;
  receivedDate: string;
  daysSinceReceived: number;
  urgency: ReplyUrgency;
  action: string;
}

export interface UserPreferences {
  targetPeriod: 1 | 2 | 3;
  priorityProjects: string[];
  noDeadlineHandling: 'medium' | 'low' | 'auto';
}
