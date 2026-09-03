/**
 * Content Studio E2B image — preinstalls skill dependencies so agents skip runtime apt/npm/pip.
 *
 * Maps to skills:
 * - pptx: pptxgenjs, markitdown, LibreOffice, Poppler, Pillow, defusedxml, lxml, react-icons/sharp
 * - docx: docx (npm), pandoc, LibreOffice, Poppler
 * - html-slides: Node only (no extra OS packages)
 */
import { Template } from 'e2b';

export const CONTENT_STUDIO_TEMPLATE_NAME =
  process.env.E2B_CONTENT_STUDIO_TEMPLATE?.trim() || 'okf-content-studio';

export const CONTENT_STUDIO_TEMPLATE_TAG =
  process.env.E2B_CONTENT_STUDIO_TEMPLATE_TAG?.trim() || '1.14';

export function defineContentStudioTemplate(options?: { fileContextPath?: string }) {
  const builder = options?.fileContextPath
    ? Template({ fileContextPath: options.fileContextPath })
    : Template();

  return (
    builder
      .fromNodeImage('22')
      .aptInstall(
        [
          'libreoffice',
          'poppler-utils',
          'pandoc',
          'python3-pip',
          'python3-dev',
          'python3-venv',
          'libxml2-dev',
          'libxslt1-dev',
          'zlib1g-dev',
          'libjpeg-dev',
          'gcc',
          'build-essential',
          'zip',
          'unzip',
        ],
        { noInstallRecommends: true },
      )
      .runCmd('ln -sf /usr/bin/python3 /usr/bin/python', { user: 'root' })
      .runCmd('pip3 install --break-system-packages "markitdown[pptx]" Pillow defusedxml lxml', {
        user: 'root',
      })
      .npmInstall(['pptxgenjs', 'docx', 'react', 'react-dom', 'react-icons', 'sharp'], { g: true })
      .runCmd('mkdir -p /home/user/content-studio/skills/docx /home/user/content-studio/skills/pptx /home/user/content-studio/skills/html-slides', {
        user: 'user',
      })
      .runCmd(
        'cd /home/user/content-studio && npm init -y && npm install docx pptxgenjs react react-dom react-icons sharp',
        { user: 'user' },
      )
      .copy(
        'agent-assets/skills/docx/scripts',
        '/home/user/content-studio/skills/docx/scripts',
      )
      .copy(
        'agent-assets/skills/pptx/scripts',
        '/home/user/content-studio/skills/pptx/scripts',
      )
      .copy(
        'agent-assets/skills/pptx/references',
        '/home/user/content-studio/skills/pptx/references',
      )
      .copy(
        'agent-assets/skills/pptx/assets',
        '/home/user/content-studio/skills/pptx/assets',
      )
      .copy(
        'agent-assets/skills/html-slides/references',
        '/home/user/content-studio/skills/html-slides/references',
      )
      .copy(
        'agent-assets/skills/html-slides/assets',
        '/home/user/content-studio/skills/html-slides/assets',
      )
      .setWorkdir('/home/user')
  );
}
