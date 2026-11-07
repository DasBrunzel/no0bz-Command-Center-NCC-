import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Markdown for chat messages. Raw HTML is never rendered; links open in a new tab. */
export default function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer nofollow" />,
        img: ({ node: _node, alt }) => <span className="ink-3">[Bild: {alt ?? "ohne Titel"}]</span>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
