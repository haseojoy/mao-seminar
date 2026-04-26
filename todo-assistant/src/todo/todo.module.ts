import { Module } from '@nestjs/common';
import { CliModule } from '../cli/cli.module';
import { GmailModule } from '../gmail/gmail.module';
import { SlackModule } from '../slack/slack.module';
import { TodoService } from './todo.service';
import { TodoFormatter } from './todo.formatter';

@Module({
  imports: [CliModule, GmailModule, SlackModule],
  providers: [TodoService, TodoFormatter],
  exports: [TodoService],
})
export class TodoModule {}
