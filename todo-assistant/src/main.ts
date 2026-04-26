import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { TodoService } from './todo/todo.service';

async function bootstrap() {
  const app = await NestFactory.createApplicationContext(AppModule, {
    logger: false,
  });
  try {
    const todoService = app.get(TodoService);
    await todoService.run();
  } finally {
    await app.close();
  }
}

bootstrap().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
