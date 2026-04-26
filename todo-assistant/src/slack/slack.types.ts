export interface SlackMessage {
  id: string;
  channel: string;
  channelType: 'public' | 'private' | 'dm';
  from: string;
  timestamp: string;
  text: string;
  isDirectMention: boolean;
  direction: 'received' | 'sent';
  hasCommitment: boolean;
  commitmentStrength?: 'strong' | 'medium';
}
