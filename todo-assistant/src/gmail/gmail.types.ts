export interface GmailMessage {
  id: string;
  subject: string;
  from: string;
  to: string;
  date: string;
  body: string;
  isRead: boolean;
  isReplied: boolean;
  direction: 'received' | 'sent';
  hasDeadline: boolean;
  deadlineDate?: string;
  project?: string;
  senderType?: 'client' | 'internal' | 'announcement';
}
