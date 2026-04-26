import { Module } from '@nestjs/common';
import { CliModule } from './cli/cli.module';
import { GmailModule } from './gmail/gmail.module';
import { SlackModule } from './slack/slack.module';
import { TodoModule } from './todo/todo.module';

@Module({
  imports: [CliModule, GmailModule, SlackModule, TodoModule],
})
export class AppModule {}
