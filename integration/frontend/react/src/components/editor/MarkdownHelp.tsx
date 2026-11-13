import { CircleHelp } from "lucide-react";
import type { ReactNode } from "react";
import { SpoilerSpan } from "../common/MarkdownContent";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

// What comments render (common/MarkdownContent: GitHub-flavoured markdown, single line breaks, <u> and Reddit's
// spoilers), each shown as it comes out, so nobody writes Reddit's ^superscript or HTML expecting it to work
const TEXT: [write: string, result: ReactNode][] = [
  ["**bold**", <strong key="b">bold</strong>],
  ["*italic*", <em key="i">italic</em>],
  ["~~strike~~", <s key="s">strike</s>],
  ["<u>underline</u>", <u key="u">underline</u>],
  [
    ">!spoiler!<",
    // The real one: tap to reveal
    <SpoilerSpan key="sp">spoiler</SpoilerSpan>,
  ],
  [
    "[link](https://...)",
    <span
      key="a"
      className="text-tfs-brand-strong dark:text-tfs-brand underline"
    >
      link
    </span>,
  ],
  [
    "`code`",
    <code key="c" className="bg-muted rounded px-1 font-mono">
      code
    </code>,
  ],
];

const BLOCKS: [write: string, result: ReactNode][] = [
  [
    "# Heading",
    <span key="h" className="text-sm font-bold">
      Heading
    </span>,
  ],
  [
    "> quote",
    <span key="q" className="border-muted-foreground/40 border-l-2 pl-2">
      quote
    </span>,
  ],
  ["- item", <span key="l">• item</span>],
  ["1. item", <span key="n">1. item</span>],
  ["```", <span key="cb">Code block, between two ``` lines</span>],
  ["| a | b |", <span key="t">Table, with |---|---| under the first row</span>],
];

// Both sections in one grid, so their columns line up
function Section({
  title,
  rows,
}: {
  title: string;
  rows: [string, ReactNode][];
}) {
  return (
    <>
      <p className="text-muted-foreground col-span-2 mt-1 text-[11px] font-medium tracking-wide uppercase first:mt-0">
        {title}
      </p>
      {rows.map(([write, result]) => (
        <div key={write} className="contents">
          <code className="bg-muted w-fit rounded px-1.5 py-0.5 font-mono text-[11px] whitespace-nowrap">
            {write}
          </code>
          <span className="text-xs">{result}</span>
        </div>
      ))}
    </>
  );
}

/** The markdown comments support, from the button beside "Markdown". */
export default function MarkdownHelp() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Markdown cheatsheet"
          title="Markdown cheatsheet"
          className="text-muted-foreground hover:bg-primary/20 hover:text-foreground flex size-6 items-center justify-center rounded-full hover:cursor-pointer"
        >
          <CircleHelp className="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(20rem,calc(100vw-1rem))] p-0">
        {/* The table scrolls when there's little room; the notes stay under it */}
        <div className="min-h-0 space-y-3 overflow-y-auto p-3">
          <p className="text-sm font-semibold">Markdown cheatsheet</p>
          <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5">
            <Section title="Text" rows={TEXT} />
            <Section title="Blocks" rows={BLOCKS} />
          </div>
        </div>
        <ul className="text-muted-foreground space-y-0.5 border-t px-3 py-2 text-[11px]">
          <li>A single line break starts a new line.</li>
          <li>Images show only from the image button&apos;s sites.</li>
          <li>Not supported: superscript (^). Most HTML is removed.</li>
        </ul>
      </PopoverContent>
    </Popover>
  );
}
