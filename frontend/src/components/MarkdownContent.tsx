import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'

type Props = {
  content: string
  className?: string
  allowHtml?: boolean
}

export function MarkdownContent({ content, className = 'markdown-body', allowHtml = false }: Props) {
  if (!content) return null
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={allowHtml ? [rehypeRaw] : []}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
