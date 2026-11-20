// @threadfs/react/markdown: comments' markdown renderer on its own, for a host's other text, so it renders exactly like
// comments without loading the widget. Also exported from the package root, for hosts that load the widget anyway. No stylesheet here: the host imports "@threadfs/react/styles.css" as for the
// widget, and the root class below brings its rules into scope.
import { MarkdownContent } from "./components/common/MarkdownContent";
import { ImageHostsContext, type ImageHosts } from "./lib/imageHosts";
import { cn } from "./lib/utils";

export type { ImageHosts };

export type ThreadFSMarkdownProps = {
  /** The text, in comments' markdown: GitHub-flavoured, single line breaks, <u>, >!spoilers!<. */
  markdown: string;
  /**
   * Which hosts' images show; others become links. Empty, the default, shows none. "any" shows every http(s) image:
   * only for text already moderated elsewhere, never for what readers write here (a tracking pixel would learn each
   * reader's IP address).
   */
  imageHosts?: ImageHosts;
  /** Headings at the text's size, for previews and excerpts. */
  compact?: boolean;
  className?: string;
};

export function ThreadFSMarkdown({ markdown, imageHosts = [], compact = false, className }: ThreadFSMarkdownProps) {
  return (
    // Long unbroken strings (links, keyboard mashing) wrap rather than stretch the page, as in a comment
    <div className={cn("threadfs-root wrap-break-word", className)}>
      <ImageHostsContext.Provider value={imageHosts}>
        <MarkdownContent markdown={markdown} compact={compact} />
      </ImageHostsContext.Provider>
    </div>
  );
}
