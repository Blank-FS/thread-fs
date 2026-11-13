import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { isAllowedImage, useImageHosts } from "@/lib/imageHosts";
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
    // No style anywhere, table cells included: a style can load an image (background: url(...)). Column alignment
    // needs none, as remark-gfm sets it with align, which react-markdown turns into a style after this.
  },
};

// Also the cheatsheet's example (editor/MarkdownHelp), so it reveals exactly as a comment's does
export function SpoilerSpan({ children }: { children?: ReactNode }) {
  const [isRevealed, setIsRevealed] = useState(false);

  return (
    <span
      role="button"
      tabIndex={0}
      aria-pressed={isRevealed}
      aria-label={isRevealed ? "Hide spoiler" : "Reveal spoiler"}
      onClick={() => setIsRevealed((value) => !value)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setIsRevealed((value) => !value);
        }
      }}
      className={cn(
        "cursor-pointer rounded bg-tfs-brand px-2 transition-colors",
        isRevealed
          ? "text-foreground bg-tfs-brand/30"
          : "text-transparent select-none",
      )}
    >
      {children}
    </span>
  );
}

/**
 * An image in comment text: shown if it's from one of the community's image hosts, else a link to it, so nothing loads
 * until someone chooses to open it (lib/imageHosts.ts).
 */
function CommentImage({
  src,
  alt,
  title,
}: {
  src?: string;
  alt?: string;
  title?: string;
}) {
  const hosts = useImageHosts();

  if (isAllowedImage(src, hosts)) {
    return (
      <img
        src={src}
        alt={alt ?? ""}
        title={title}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        className="my-2 max-h-100 max-w-full rounded-lg"
      />
    );
  }

  const label = alt?.trim() || "image";
  if (!src || !/^https?:\/\//i.test(src)) return <>{label}</>;

  return (
    <a
      href={src}
      title={title}
      target="_blank"
      rel="noreferrer noopener nofollow ugc"
      className="text-tfs-brand-strong dark:hover:text-tfs-brand underline"
    >
      {label}
    </a>
  );
}

export function MarkdownContent({ markdown }: { markdown: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      rehypePlugins={[rehypeRaw, [rehypeSanitize, markdownSchema]]}
      components={{
        h1: ({ node, ...props }) => (
          <h1
            className={cn(
              "my-4 border-b border-tfs-brand/30 pb-2 font-bold tracking-tight",
              "text-lg",
            )}
            {...props}
          />
        ),
        h2: ({ node, ...props }) => (
          <h2
            className={cn(
              "my-4 border-b border-tfs-brand/30 pb-2 font-bold tracking-tight",
              "text-base",
            )}
            {...props}
          />
        ),
        h3: ({ node, ...props }) => (
          <h3
            className={cn(
              "my-4 font-bold tracking-tight",
              "text-sm",
            )}
            {...props}
          />
        ),
        p: ({ node, ...props }) => (
          <p className="mb-2 text-sm leading-6 last:mb-0" {...props} />
        ),
        a: ({ node, ...props }) => (
          <a
            className="text-tfs-brand-strong dark:hover:text-tfs-brand underline"
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
        img: ({ node, alt, src, title }) => (
          <CommentImage
            src={typeof src === "string" ? src : undefined}
            alt={alt}
            title={title}
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
            className="bg-primary/10 my-2 rounded-r-lg border-l-4 border-tfs-brand/30 p-4 italic [&>p]:m-0"
            {...props}
          />
        ),
        span: ({ node, className, children, ...props }) => {
          if (className === "threadfs-spoiler") {
            return <SpoilerSpan>{children}</SpoilerSpan>;
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
