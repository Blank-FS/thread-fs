import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

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
            className="my-4 text-2xl font-bold tracking-tight sm:text-3xl"
            {...props}
          />
        ),
        h2: ({ node, ...props }) => (
          <h2
            className="mt-8 mb-4 border-b border-cyan-200 pb-2 text-xl font-bold sm:text-2xl"
            {...props}
          />
        ),
        h3: ({ node, ...props }) => (
          <h3
            className="mt-6 mb-2 text-lg font-semibold sm:text-xl"
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
          <ul className="mb-4 list-disc space-y-2 pl-6" {...props} />
        ),
        ol: ({ node, ...props }) => (
          <ol className="mb-4 list-decimal space-y-2 pl-6" {...props} />
        ),
        li: ({ node, ...props }) => <li className="pl-1" {...props} />,
        pre: ({ children }) => (
          <pre className="bg-secondary-foreground/10 my-4 overflow-x-auto rounded-lg p-3 px-6">
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
            <code
              className="bg-secondary-foreground/10 rounded px-1 py-0.5 font-mono text-sm text-wrap"
              {...props}
            >
              {children}
            </code>
          );
        },
        u: ({ node, ...props }) => (
          <u className="underline decoration-solid" {...props} />
        ),
        blockquote: ({ node, ...props }) => (
          <blockquote
            className="text-muted-foreground my-4 rounded-r-lg border-l-4 border-cyan-200 bg-cyan-200/20 px-4 py-2 italic"
            {...props}
          />
        ),
        span: ({ node, className, children, ...props }) => {
          if (className === "threadfs-spoiler") {
            return (
              <span
                className="hover:text-foreground rounded bg-cyan-200 px-1 text-transparent transition-colors hover:bg-cyan-200/20 focus:text-white"
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
