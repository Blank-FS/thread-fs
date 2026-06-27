import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";
import { preprocessRedditMarkdown } from "./markdownUtils";

const markdownSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), "span", "u"],
  attributes: {
    ...defaultSchema.attributes,
    span: [
      ...(defaultSchema.attributes?.span ?? []),
      ["className", "threadfs-spoiler"],
    ],
    a: [
      ...(defaultSchema.attributes?.a ?? []),
      "href",
      "title",
      "target",
      "rel",
    ],
    img: [...(defaultSchema.attributes?.img ?? []), "alt", "title"],
    // GFM table alignment is emitted as inline style by remark-gfm; scope
    // the allowance to table cells only, not the whole document.
    th: [...(defaultSchema.attributes?.th ?? []), "style"],
    td: [...(defaultSchema.attributes?.td ?? []), "style"],
  },
};

export function MarkdownContent({ markdown }: { markdown: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      rehypePlugins={[rehypeRaw, [rehypeSanitize, markdownSchema]]}
      components={{
        h1: ({ node, ...props }) => (
          <h1
            className={cn(
              "my-4 border-b border-cyan-200/30 pb-2 font-bold tracking-tight",
              "text-2xl sm:text-3xl",
            )}
            {...props}
          />
        ),
        h2: ({ node, ...props }) => (
          <h2
            className={cn(
              "my-4 border-b border-cyan-200/30 pb-2 font-bold tracking-tight",
              "text-xl sm:text-2xl",
            )}
            {...props}
          />
        ),
        h3: ({ node, ...props }) => (
          <h3
            className={cn(
              "my-4 font-bold tracking-tight",
              "text-lg sm:text-xl",
            )}
            {...props}
          />
        ),
        p: ({ node, ...props }) => (
          <p className="mb-4 text-base leading-relaxed" {...props} />
        ),
        a: ({ node, ...props }) => (
          <a
            className="text-cyan-500 underline hover:text-cyan-200"
            target="_blank"
            rel="noreferrer noopener"
            {...props}
          />
        ),
        ul: ({ node, ...props }) => (
          <ul className="list-outside list-disc pl-6" {...props} />
        ),
        ol: ({ node, ...props }) => (
          <ol className="list-outside list-decimal pl-6" {...props} />
        ),
        img: ({ node, alt, ...props }) => (
          <img
            alt={alt ?? ""}
            loading="lazy"
            className="my-2 max-h-100 max-w-full rounded-lg"
            {...props}
          />
        ),
        table: ({ node, ...props }) => (
          <div className="my-4 overflow-x-auto rounded-lg border">
            <table className="w-full border-collapse text-sm" {...props} />
          </div>
        ),
        thead: ({ node, ...props }) => (
          <thead className="bg-secondary-foreground/10" {...props} />
        ),
        tr: ({ node, ...props }) => (
          <tr className="border-b last:border-b-0" {...props} />
        ),
        th: ({ node, ...props }) => (
          <th className="px-3 py-2 text-left font-semibold" {...props} />
        ),
        td: ({ node, ...props }) => <td className="px-3 py-2" {...props} />,
        pre: ({ children }) => (
          <pre className="bg-primary/10 my-4 overflow-x-auto rounded-lg p-3">
            {children}
          </pre>
        ),
        code: ({ className, children, ...props }) => {
          const isBlock = className?.includes("language-");

          if (isBlock) {
            return (
              <code
                className={`${className} rounded font-mono text-sm text-wrap`}
                {...props}
              >
                {children}
              </code>
            );
          }

          return (
            <code className="rounded font-mono text-sm text-wrap" {...props}>
              {children}
            </code>
          );
        },
        u: ({ node, ...props }) => (
          <u className="underline decoration-solid" {...props} />
        ),
        blockquote: ({ node, ...props }) => (
          <blockquote
            className="bg-primary/10 my-2 rounded-r-lg border-l-4 border-cyan-200/30 p-4 italic [&>p]:m-0"
            {...props}
          />
        ),
        span: ({ node, className, children, ...props }) => {
          if (className === "threadfs-spoiler") {
            return (
              <span
                className="hover:text-foreground rounded bg-cyan-200 px-2 text-transparent transition-colors hover:bg-cyan-200/30"
                tabIndex={0}
              >
                {children}
              </span>
            );
          }

          return (
            <span className={className} {...props}>
              {children}
            </span>
          );
        },
      }}
    >
      {preprocessRedditMarkdown(markdown)}
    </ReactMarkdown>
  );
}
