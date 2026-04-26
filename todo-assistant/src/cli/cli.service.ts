import * as readline from 'readline';
import { Injectable, OnModuleDestroy } from '@nestjs/common';

@Injectable()
export class CliService implements OnModuleDestroy {
  private rl: readline.Interface;
  private bufferedLines: string[] = [];
  private waitingResolvers: Array<(line: string) => void> = [];
  private closed = false;

  constructor() {
    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: false,
    });

    this.rl.on('line', (line) => {
      const trimmed = line.trim();
      if (this.waitingResolvers.length > 0) {
        const resolve = this.waitingResolvers.shift()!;
        resolve(trimmed);
      } else {
        this.bufferedLines.push(trimmed);
      }
    });

    this.rl.on('close', () => {
      this.closed = true;
      // Drain any waiting resolvers with empty string
      for (const resolve of this.waitingResolvers) {
        resolve('');
      }
      this.waitingResolvers = [];
    });
  }

  question(prompt: string): Promise<string> {
    process.stdout.write(prompt);
    if (this.bufferedLines.length > 0) {
      const line = this.bufferedLines.shift()!;
      process.stdout.write(line + '\n');
      return Promise.resolve(line);
    }
    if (this.closed) {
      return Promise.resolve('');
    }
    return new Promise((resolve) => {
      this.waitingResolvers.push(resolve);
    });
  }

  async askChoice(prompt: string, choices: string[], defaultIndex = 0): Promise<number> {
    const separator = '━'.repeat(35);
    process.stdout.write(`\n${separator}\n`);
    process.stdout.write(`${prompt}\n`);
    choices.forEach((c, i) => process.stdout.write(`  ${i + 1}: ${c}\n`));

    while (true) {
      const answer = await this.question(
        `選択してください [1-${choices.length}] (デフォルト: ${defaultIndex + 1}): `,
      );
      if (answer === '') return defaultIndex;
      const num = parseInt(answer, 10);
      if (!isNaN(num) && num >= 1 && num <= choices.length) return num - 1;
      process.stdout.write(`有効な番号を入力してください (1-${choices.length})\n`);
    }
  }

  onModuleDestroy() {
    if (!this.closed) this.rl.close();
  }
}
