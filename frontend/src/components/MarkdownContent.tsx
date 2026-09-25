import ReactMarkdown, { defaultUrlTransform } from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'

type Props = {
  content: string
  className?: string
  allowHtml?: boolean
  resolveImageSrc?: (src: string | undefined) => string | undefined
}

export function MarkdownContent({
  content,
  className = 'markdown-body',
  allowHtml = false,
  resolveImageSrc,
}: Props) {
  if (!content) return null

  const urlTransform = resolveImageSrc
    ? (url: string) => defaultUrlTransform(resolveImageSrc(url) ?? url)
    : defaultUrlTransform

  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={allowHtml ? [rehypeRaw] : []}
        urlTransform={urlTransform}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
