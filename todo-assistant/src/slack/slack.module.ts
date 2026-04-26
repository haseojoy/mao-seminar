import { Module } from '@nestjs/common';
import { CliModule } from '../cli/cli.module';
import { SlackService } from './slack.service';

@Module({
  imports: [CliModule],
  providers: [SlackService],
  exports: [SlackService],
})
export class SlackModule {}
