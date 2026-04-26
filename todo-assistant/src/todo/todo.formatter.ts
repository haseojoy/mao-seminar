import { Injectable } from '@nestjs/common';
import { TodoItem, ReplyItem } from './todo.types';

@Injectable()
export class TodoFormatter {
  format(
    todos: TodoItem[],
    replies: ReplyItem[],
    remainingCount: number,
    timeEstimate: string,
  ): string {
    const today = new Date().toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).replace(/\//g, '-');

    const lines: string[] = [];
    lines.push(`本日のタスク整理（${today}）`);
    lines.push('');

    const high = todos.filter((t) => t.priority === 'high');
    const medium = todos.filter((t) => t.priority === 'medium');
    const low = todos.filter((t) => t.priority === 'low');

    if (high.length) {
      lines.push('【優先度：高】');
      high.forEach((t) => {
        const deadline = t.deadline ? ` → ${t.deadline}` : '';
        lines.push(`- ${t.title}${deadline}（${t.source}: ${t.sender}、${t.date}）`);
      });
      lines.push('');
    }

    if (medium.length) {
      lines.push('【優先度：中】');
      medium.forEach((t) => {
        const deadline = t.deadline ? ` → ${t.deadline}` : '';
        lines.push(`- ${t.title}${deadline}（${t.source}: ${t.sender}、${t.date}）`);
      });
      lines.push('');
    }

    if (low.length) {
      lines.push('【優先度：低】');
      low.forEach((t) => {
        const deadline = t.deadline ? ` → ${t.deadline}` : '';
        lines.push(`- ${t.title}${deadline}（${t.source}: ${t.date}）`);
      });
      lines.push('');
    }

    if (replies.length) {
      lines.push('【返信すべきメール】');
      replies.forEach((r) => {
        const emoji = r.urgency === 'red' ? '🔴' : r.urgency === 'yellow' ? '🟡' : '🟢';
        const days = r.daysSinceReceived > 0 ? `受信から${r.daysSinceReceived}日、未返信` : '未返信';
        lines.push(`- ${emoji} ${r.subject}（${days}） → ${r.action}`);
      });
      lines.push('');
    }

    if (remainingCount > 0) {
      lines.push(`他に${remainingCount}件のタスクがあります`);
      lines.push('');
    }

    lines.push('本日のタスク量評価:');
    lines.push(timeEstimate);

    return lines.join('\n');
  }
}
