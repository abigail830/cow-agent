#!/usr/bin/env tsx
/**
 * Build and publish the Content Studio E2B template.
 *
 * Usage:
 *   E2B_API_KEY=... npm run e2b:build-content-studio-template
 */
import '../../scripts/load-env.ts';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Template } from 'e2b';
import {
  CONTENT_STUDIO_TEMPLATE_NAME,
  CONTENT_STUDIO_TEMPLATE_TAG,
  defineContentStudioTemplate,
} from './template.ts';

const backendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

async function main() {
  const apiKey = process.env.E2B_API_KEY?.trim();
  if (!apiKey) {
    throw new Error('E2B_API_KEY is required to build the template');
  }

  const template = defineContentStudioTemplate({ fileContextPath: backendRoot });
  const name = `${CONTENT_STUDIO_TEMPLATE_NAME}:${CONTENT_STUDIO_TEMPLATE_TAG}`;

  console.log(`[e2b] Building template ${name} ...`);
  const info = await Template.build(template, name, {
    apiKey,
    onBuildLogs: (log) => {
      const prefix = log.level === 'error' ? '[e2b:error]' : '[e2b]';
      console.log(prefix, log.message);
    },
  });

  console.log('[e2b] Build finished:', {
    templateId: info.templateId,
    buildId: info.buildId,
    alias: CONTENT_STUDIO_TEMPLATE_NAME,
    tag: CONTENT_STUDIO_TEMPLATE_TAG,
  });
  console.log(
    `[e2b] Set agent sandbox.templateId to "${CONTENT_STUDIO_TEMPLATE_NAME}:${CONTENT_STUDIO_TEMPLATE_TAG}" (bare alias also works — platform resolves the tag).`,
  );
}

main().catch((error) => {
  console.error('[e2b] Build failed:', error instanceof Error ? error.message : error);
  if (error instanceof Error && error.stack) console.error(error.stack);
  process.exit(1);
});
