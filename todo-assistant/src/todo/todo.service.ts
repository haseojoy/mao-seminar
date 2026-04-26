import { Injectable } from '@nestjs/common';
import { GmailService } from '../gmail/gmail.service';
import { GmailMessage } from '../gmail/gmail.types';
import { SlackService } from '../slack/slack.service';
import { SlackMessage } from '../slack/slack.types';
import { CliService } from '../cli/cli.service';
import { TodoFormatter } from './todo.formatter';
import { TodoItem, ReplyItem, UserPreferences, Priority } from './todo.types';

const TODAY = '2026-04-26';
const TODAY_DATE = new Date(TODAY);

function parseDate(dateStr: string): Date {
  return new Date(dateStr.substring(0, 10));
}

function daysSince(dateStr: string): number {
  const d = parseDate(dateStr);
  return Math.floor((TODAY_DATE.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
}

function isToday(dateStr: string): boolean {
  return dateStr.startsWith(TODAY);
}

function isTomorrow(dateStr: string): boolean {
  return dateStr.startsWith('2026-04-27');
}

function isThisWeek(dateStr: string): boolean {
  const d = parseDate(dateStr);
  const weekEnd = new Date('2026-05-02');
  return d <= weekEnd && d >= TODAY_DATE;
}

function containsAny(text: string, keywords: string[]): boolean {
  return keywords.some((kw) => text.includes(kw));
}

function matchesPriorityProjects(text: string, projects: string[]): boolean {
  if (!projects.length) return false;
  return projects.some((p) => text.includes(p));
}

@Injectable()
export class TodoService {
  constructor(
    private readonly gmailService: GmailService,
    private readonly slackService: SlackService,
    private readonly cliService: CliService,
    private readonly todoFormatter: TodoFormatter,
  ) {}

  async run(): Promise<void> {
    // Step 1: Collect
    console.log('📥 GmailとSlackから情報を収集しています...');
    const privateAnswer = await this.cliService.question(
      'Slackのプライベートメッセージも確認してよいですか？(y/n) ',
    );
    const includePrivate = privateAnswer.toLowerCase() === 'y';

    const [gmailMessages, slackMessages] = await Promise.all([
      this.gmailService.fetchMessages(),
      this.slackService.fetchMessages(includePrivate),
    ]);

    // Step 2: Clarifying questions
    const prefs = await this.askClarifyingQuestions();

    // Step 3: Classify and output
    const cutoff = this.getCutoffDate(prefs.targetPeriod);
    const filteredGmail = gmailMessages.filter((m) => parseDate(m.date) >= cutoff);
    const filteredSlack = slackMessages.filter((m) => parseDate(m.timestamp) >= cutoff);

    const { todos, replies } = this.classifyMessages(filteredGmail, filteredSlack, prefs);

    const sorted = this.sortTodos(todos);
    const MAX = 10;
    const remainingCount = sorted.length > MAX ? sorted.length - MAX : 0;
    const displayTodos = sorted.slice(0, MAX);

    const timeEstimate = this.estimateTime(displayTodos);
    const output = this.todoFormatter.format(displayTodos, replies, remainingCount, timeEstimate);

    console.log('\n' + '━'.repeat(35));
    console.log('');
    console.log(output);
  }

  private async askClarifyingQuestions(): Promise<UserPreferences> {
    const periodIdx = await this.cliService.askChoice(
      'どの期間のメール・チャットを対象にしますか？',
      ['昨日〜今日（デフォルト）', '過去3日間', '過去1週間'],
      0,
    );

    const projectIdx = await this.cliService.askChoice(
      '今日、特に優先すべきプロジェクト・クライアントはありますか？',
      ['特にない', 'ある（テキスト入力）'],
      0,
    );

    let priorityProjects: string[] = [];
    if (projectIdx === 1) {
      const input = await this.cliService.question(
        'プロジェクト・クライアント名を入力してください（複数の場合はカンマ区切り）: ',
      );
      priorityProjects = input
        .split(/[,、，]/)
        .map((s) => s.trim())
        .filter(Boolean);
    }

    const noDeadlineIdx = await this.cliService.askChoice(
      '期限が明記されていないタスクはどう分類しますか？',
      ['優先度：中に分類', '優先度：低に分類', '内容で個別に判断する'],
      0,
    );

    const noDeadlineHandling = (['medium', 'low', 'auto'] as const)[noDeadlineIdx];
    const targetPeriod = ([1, 2, 3] as const)[periodIdx];

    return { targetPeriod, priorityProjects, noDeadlineHandling };
  }

  private getCutoffDate(period: 1 | 2 | 3): Date {
    if (period === 1) return new Date('2026-04-25');
    if (period === 2) return new Date('2026-04-23');
    return new Date('2026-04-19');
  }

  private classifyMessages(
    gmailMessages: GmailMessage[],
    slackMessages: SlackMessage[],
    prefs: UserPreferences,
  ): { todos: TodoItem[]; replies: ReplyItem[] } {
    const todos: TodoItem[] = [];
    const replies: ReplyItem[] = [];
    const seen = new Set<string>();

    const STRONG_COMMITMENT = ['今日中に', '今日送', '今日確認', '今日対応', '本日中', 'すぐに'];
    const MEDIUM_COMMITMENT = ['対応します', 'やります', '確認します', '送ります', '進めます', '週末まで', '来週まで'];
    const URGENT_KEYWORDS = ['急ぎ', '緊急', '今日中'];

    for (const msg of gmailMessages) {
      const fullText = `${msg.subject} ${msg.body} ${msg.from}`;
      const isHighProject = matchesPriorityProjects(fullText, prefs.priorityProjects);

      if (msg.direction === 'sent') {
        const isStrongCommitment = containsAny(msg.body, STRONG_COMMITMENT);
        const isMediumCommitment = containsAny(msg.body, MEDIUM_COMMITMENT);

        if (!isStrongCommitment && !isMediumCommitment) continue;

        let priority: Priority;
        if (isStrongCommitment && msg.deadlineDate && (isToday(msg.deadlineDate) || isTomorrow(msg.deadlineDate))) {
          priority = 'high';
        } else if (isHighProject) {
          priority = 'high';
        } else if (isStrongCommitment) {
          priority = 'high';
        } else {
          priority = 'medium';
        }

        const title = this.buildGmailSentTitle(msg.subject, msg.body);
        const key = `gmail-sent-${msg.id}`;
        if (!seen.has(key)) {
          seen.add(key);
          todos.push({
            title,
            priority,
            source: 'Gmail',
            sender: this.extractName(msg.to),
            date: msg.date,
            deadline: msg.deadlineDate,
            project: msg.project,
          });
        }
        continue;
      }

      // Received messages
      let priority: Priority;

      if (
        msg.deadlineDate &&
        (isToday(msg.deadlineDate) || isTomorrow(msg.deadlineDate))
      ) {
        priority = 'high';
      } else if (
        !msg.isReplied &&
        msg.senderType === 'client' &&
        daysSince(msg.date) >= 2
      ) {
        priority = 'high';
      } else if (containsAny(msg.subject, URGENT_KEYWORDS)) {
        priority = 'high';
      } else if (isHighProject) {
        priority = 'high';
      } else if (msg.deadlineDate && isThisWeek(msg.deadlineDate)) {
        priority = 'medium';
      } else if (!msg.hasDeadline) {
        if (prefs.noDeadlineHandling === 'medium') {
          priority = 'medium';
        } else if (prefs.noDeadlineHandling === 'low') {
          priority = 'low';
        } else {
          // auto
          if (msg.senderType === 'client') priority = 'medium';
          else if (msg.senderType === 'announcement') priority = 'low';
          else priority = 'medium';
        }
      } else {
        priority = 'low';
      }

      // Skip pure info announcements with no action required unless overridden
      if (
        msg.senderType === 'announcement' &&
        priority === 'low' &&
        !containsAny(msg.subject, ['経費', '請求', '精算'])
      ) {
        // still add but as low
      }

      const title = `${msg.subject}への対応`;
      const key = `gmail-recv-${msg.id}`;
      if (!seen.has(key)) {
        seen.add(key);
        todos.push({
          title,
          priority,
          source: 'Gmail',
          sender: this.extractName(msg.from),
          date: msg.date,
          deadline: msg.deadlineDate,
          project: msg.project,
        });
      }

      // Reply tracking
      if (msg.direction === 'received' && !msg.isReplied) {
        const days = daysSince(msg.date);
        let urgency: ReplyItem['urgency'];
        let action: string;

        if (days >= 2 && msg.senderType === 'client') {
          urgency = 'red';
          action = '今日中に返信';
        } else if (msg.senderType === 'announcement') {
          urgency = 'green';
          action = '急がない';
        } else if (priority === 'high' || priority === 'medium') {
          urgency = 'yellow';
          action = '関連作業完了後に返信';
        } else {
          urgency = 'green';
          action = '急がない';
        }

        replies.push({
          subject: msg.subject,
          sender: this.extractName(msg.from),
          receivedDate: msg.date,
          daysSinceReceived: days,
          urgency,
          action,
        });
      }
    }

    // Slack messages
    for (const msg of slackMessages) {
      const fullText = `${msg.text} ${msg.channel}`;
      const isHighProject = matchesPriorityProjects(fullText, prefs.priorityProjects);

      if (msg.direction === 'sent' && msg.hasCommitment) {
        let priority: Priority;
        if (msg.commitmentStrength === 'strong') {
          priority = isHighProject ? 'high' : 'high';
        } else {
          priority = isHighProject ? 'high' : 'medium';
        }

        const title = `${msg.channel}でのコミットメント実行: ${this.truncate(msg.text, 30)}`;
        const key = `slack-sent-${msg.id}`;
        if (!seen.has(key)) {
          seen.add(key);
          todos.push({
            title,
            priority,
            source: 'Slack',
            sender: msg.from,
            date: msg.timestamp.substring(0, 10),
          });
        }
        continue;
      }

      if (msg.direction === 'received' && msg.isDirectMention) {
        // Skip bot announcements
        if (msg.from === 'bot') continue;

        let priority: Priority;
        if (containsAny(msg.text, URGENT_KEYWORDS) || isHighProject) {
          priority = 'high';
        } else if (prefs.noDeadlineHandling === 'low') {
          priority = 'low';
        } else {
          priority = 'medium';
        }

        const title = `${msg.from}への${msg.channel}での返信・対応`;
        const key = `slack-recv-${msg.id}`;
        if (!seen.has(key)) {
          seen.add(key);
          todos.push({
            title,
            priority,
            source: 'Slack',
            sender: msg.from,
            date: msg.timestamp.substring(0, 10),
          });
        }
      }
    }

    // Sort replies: red first, then yellow, then green
    const urgencyOrder = { red: 0, yellow: 1, green: 2 };
    replies.sort((a, b) => urgencyOrder[a.urgency] - urgencyOrder[b.urgency]);

    return { todos, replies };
  }

  private sortTodos(todos: TodoItem[]): TodoItem[] {
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    return [...todos].sort((a, b) => {
      const po = priorityOrder[a.priority] - priorityOrder[b.priority];
      if (po !== 0) return po;
      // Within same priority, earlier deadline first
      if (a.deadline && b.deadline) return a.deadline.localeCompare(b.deadline);
      if (a.deadline) return -1;
      if (b.deadline) return 1;
      return 0;
    });
  }

  private estimateTime(todos: TodoItem[]): string {
    const hours = todos.reduce((acc, t) => {
      return acc + (t.priority === 'high' ? 1.5 : t.priority === 'medium' ? 1.0 : 0.5);
    }, 0);
    const ratio = hours / 8;
    const label =
      ratio <= 0.6 ? '少なめ' : ratio <= 1.0 ? '適切' : ratio <= 1.4 ? 'やや多め' : '多すぎ';
    let advice = '';
    if (ratio > 1.4) {
      advice = '\n→ 午前中に優先度「高」を片付けると、午後に余裕が生まれます。';
    }
    return `推定作業時間: 約${hours}時間 / 8時間（${label}）${advice}`;
  }

  private extractName(address: string): string {
    const match = address.match(/^([^<]+)/);
    return match ? match[1].trim() : address;
  }

  private buildGmailSentTitle(subject: string, body: string): string {
    if (body.includes('送ります') || body.includes('お送り')) return `${subject}の送付`;
    if (body.includes('確認')) return `${subject}の確認`;
    if (body.includes('対応')) return `${subject}への対応`;
    return `${subject}のフォローアップ`;
  }

  private truncate(text: string, maxLen: number): string {
    return text.length <= maxLen ? text : text.substring(0, maxLen) + '…';
  }
}
