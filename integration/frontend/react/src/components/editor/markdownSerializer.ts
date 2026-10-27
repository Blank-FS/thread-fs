// Converts between stored markdown and the rich editor's Lexical nodes.
//
// Rich text is a subset of markdown: what the toolbar can make (paragraphs, line breaks, quotes, lists, bold,
// italic, underline, strikethrough and spoilers). Markdown is parsed with the same remark plugins MarkdownContent
// renders with, so the rich editor shows a comment exactly the way it's displayed. Anything outside the subset
// (headings, links, code, images, tables, HTML...) makes isRichTextCompatible() false, and the comment is edited
// as markdown instead.

import {
  $createListItemNode,
  $createListNode,
  $isListItemNode,
  $isListNode,
  ListItemNode,
  ListNode,
} from "@lexical/list";
import { $createQuoteNode, $isQuoteNode, QuoteNode } from "@lexical/rich-text";
import {
  $createLineBreakNode,
  $createParagraphNode,
  $createTextNode,
  $getRoot,
  $isElementNode,
  $isLineBreakNode,
  $isTextNode,
  createEditor,
  ElementNode,
  LexicalNode,
  ParagraphNode,
  TextFormatType,
  TextNode,
} from "lexical";
import type * as Mdast from "mdast";
import { gfmStrikethroughToMarkdown } from "mdast-util-gfm-strikethrough";
import {
  toMarkdown,
  type Handle,
  type Options as ToMarkdownOptions,
} from "mdast-util-to-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import { unified } from "unified";
import { preprocessRedditMarkdown } from "../common/markdownUtils";

// The node types the rich editor uses. Leaving out headings and links also keeps paste from creating them.
export const RICH_EDITOR_NODES = [
  ParagraphNode,
  TextNode,
  QuoteNode,
  ListItemNode,
  ListNode,
];

// --- Parse: markdown -> Lexical ---

class UnsupportedMarkdownError extends Error {}

// Same remark plugins as MarkdownContent
const markdownProcessor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkBreaks);

function parseMarkdown(markdown: string): Mdast.Root {
  // MarkdownContent turns >!spoilers!< into spans before parsing, so they reach the tree as inline HTML
  const tree = markdownProcessor.parse(preprocessRedditMarkdown(markdown));
  return markdownProcessor.runSync(tree) as Mdast.Root;
}

// Inline HTML the editor understands, as text formats it switches on and off
const HTML_FORMAT_TAGS: Record<string, [TextFormatType, boolean]> = {
  "<u>": ["underline", true],
  "</u>": ["underline", false],
  '<span class="threadfs-spoiler">': ["highlight", true],
  "</span>": ["highlight", false],
};

function appendText(
  target: ElementNode,
  value: string,
  formats: ReadonlySet<TextFormatType>,
): void {
  value.split(/\r?\n/).forEach((line, index) => {
    if (index > 0) target.append($createLineBreakNode());
    if (line.length === 0) return;
    const textNode = $createTextNode(line);
    formats.forEach((format) => textNode.toggleFormat(format));
    target.append(textNode);
  });
}

// A bare URL (https://..., www..., an email) is linked by MarkdownContent on its own, so it's plain text here
function isBareUrl(link: Mdast.Link): boolean {
  const [child, ...rest] = link.children;
  if (rest.length > 0 || child?.type !== "text") return false;
  return [
    child.value,
    `http://${child.value}`,
    `mailto:${child.value}`,
  ].includes(link.url);
}

function appendPhrasing(
  target: ElementNode,
  nodes: Mdast.PhrasingContent[],
  inheritedFormats: ReadonlySet<TextFormatType>,
): void {
  // Formats switched on by inline HTML; they must be switched off again within the same parent
  let formats = new Set(inheritedFormats);

  for (const node of nodes) {
    switch (node.type) {
      case "text":
        appendText(target, node.value, formats);
        break;
      case "break":
        target.append($createLineBreakNode());
        break;
      case "strong":
        appendPhrasing(target, node.children, new Set([...formats, "bold"]));
        break;
      case "emphasis":
        appendPhrasing(target, node.children, new Set([...formats, "italic"]));
        break;
      case "delete":
        appendPhrasing(
          target,
          node.children,
          new Set([...formats, "strikethrough"]),
        );
        break;
      case "link":
        if (!isBareUrl(node)) throw new UnsupportedMarkdownError("link");
        appendPhrasing(target, node.children, formats);
        break;
      case "html": {
        const tag = HTML_FORMAT_TAGS[node.value];
        if (!tag) throw new UnsupportedMarkdownError(`html ${node.value}`);
        const [format, on] = tag;
        if (formats.has(format) === on) {
          throw new UnsupportedMarkdownError(`unbalanced ${node.value}`);
        }
        formats = new Set(formats);
        if (on) formats.add(format);
        else formats.delete(format);
        break;
      }
      default:
        throw new UnsupportedMarkdownError(node.type);
    }
  }

  if (formats.size !== inheritedFormats.size) {
    throw new UnsupportedMarkdownError("unclosed inline html");
  }
}

function convertList(list: Mdast.List): ListNode {
  const listNode = list.ordered
    ? $createListNode("number", list.start ?? 1)
    : $createListNode("bullet");

  for (const item of list.children) {
    if (item.checked !== null && item.checked !== undefined) {
      throw new UnsupportedMarkdownError("task list");
    }

    const [first, ...rest] = item.children;
    const nestedLists = first?.type === "paragraph" ? rest : item.children;
    if (nestedLists.some((child) => child.type !== "list")) {
      throw new UnsupportedMarkdownError("complex list item");
    }

    const itemNode = $createListItemNode();
    if (first?.type === "paragraph") {
      appendPhrasing(itemNode, first.children, new Set());
    }
    listNode.append(itemNode);

    // Lexical nests a list inside its own list item, after the item it belongs to
    for (const nested of nestedLists as Mdast.List[]) {
      const wrapper = $createListItemNode();
      wrapper.append(convertList(nested));
      listNode.append(wrapper);
    }
  }

  return listNode;
}

function convertBlock(node: Mdast.RootContent): LexicalNode {
  switch (node.type) {
    case "paragraph": {
      const paragraph = $createParagraphNode();
      appendPhrasing(paragraph, node.children, new Set());
      return paragraph;
    }
    case "blockquote": {
      const [first, ...rest] = node.children;
      if (rest.length > 0 || (first && first.type !== "paragraph")) {
        throw new UnsupportedMarkdownError("complex blockquote");
      }
      const quote = $createQuoteNode();
      if (first) appendPhrasing(quote, first.children, new Set());
      return quote;
    }
    case "list":
      return convertList(node);
    default:
      throw new UnsupportedMarkdownError(node.type);
  }
}

// Throws UnsupportedMarkdownError for markdown the rich editor can't represent
function convertMarkdown(markdown: string): LexicalNode[] {
  return parseMarkdown(markdown).children.map(convertBlock);
}

export function $convertFromMarkdownString(markdown: string): void {
  const root = $getRoot();
  root.clear();

  let blocks: LexicalNode[];
  try {
    blocks = convertMarkdown(markdown);
  } catch (error) {
    if (!(error instanceof UnsupportedMarkdownError)) throw error;
    // Callers check isRichTextCompatible first; if they didn't, show the raw markdown rather than lose it
    const paragraph = $createParagraphNode();
    appendText(paragraph, markdown, new Set());
    blocks = [paragraph];
  }

  if (blocks.length === 0) blocks = [$createParagraphNode()];
  root.append(...blocks);
}

const compatibilityEditor = createEditor({
  namespace: "ThreadFSCompatibility",
  nodes: RICH_EDITOR_NODES,
  onError(error: Error) {
    throw error;
  },
});

// Whether the rich editor can show this markdown. If not, it's edited as markdown, since loading it into the rich
// editor would turn the syntax it doesn't support into plain text.
export function isRichTextCompatible(markdown: string): boolean {
  let compatible = true;
  compatibilityEditor.update(
    () => {
      try {
        convertMarkdown(markdown);
      } catch (error) {
        if (!(error instanceof UnsupportedMarkdownError)) throw error;
        compatible = false;
      }
    },
    { discrete: true },
  );
  return compatible;
}

// --- Serialize: Lexical -> markdown ---

// Underline and spoilers aren't markdown; they're written as <u>...</u> and >!...!< by the handlers below
interface Underline extends Mdast.Parent {
  type: "underline";
  children: Mdast.PhrasingContent[];
}

interface Spoiler extends Mdast.Parent {
  type: "spoiler";
  children: Mdast.PhrasingContent[];
}

declare module "mdast" {
  interface PhrasingContentMap {
    underline: Underline;
    spoiler: Spoiler;
  }
  interface RootContentMap {
    underline: Underline;
    spoiler: Spoiler;
  }
}

type Phrasing = Mdast.PhrasingContent;

// Text formats as wrapper nodes, innermost first
const FORMAT_WRAPPERS: [TextFormatType, Phrasing["type"]][] = [
  ["italic", "emphasis"],
  ["bold", "strong"],
  ["strikethrough", "delete"],
  ["underline", "underline"],
  ["highlight", "spoiler"],
];

const MERGEABLE_TYPES = new Set<string>(
  FORMAT_WRAPPERS.map(([, type]) => type),
);

function textToPhrasing(node: TextNode): Phrasing {
  const value = node.getTextContent();
  let phrasing: Phrasing = node.hasFormat("code")
    ? { type: "inlineCode", value }
    : { type: "text", value };

  for (const [format, type] of FORMAT_WRAPPERS) {
    if (node.hasFormat(format)) {
      phrasing = { type, children: [phrasing] } as Phrasing;
    }
  }
  return phrasing;
}

// Joins neighbours with the same formatting, so **a** next to ***b*** becomes **a*b*** rather than **a*****b***.
// Lexical line breaks carry no formatting, so a format spanning lines is also joined across the break between them.
function mergeAdjacent(nodes: Phrasing[]): Phrasing[] {
  const merged: Phrasing[] = [];

  for (const node of nodes) {
    const previous = merged[merged.length - 1];
    const beforeBreak =
      previous?.type === "break" ? merged[merged.length - 2] : undefined;

    if (previous?.type === "text" && node.type === "text") {
      merged[merged.length - 1] = {
        type: "text",
        value: previous.value + node.value,
      };
    } else if (
      MERGEABLE_TYPES.has(node.type) &&
      (previous?.type === node.type || beforeBreak?.type === node.type)
    ) {
      const target = (
        previous?.type === node.type ? previous : beforeBreak
      ) as Mdast.Parent;
      const between: Phrasing[] = target === previous ? [] : [previous!];
      merged.splice(merged.indexOf(target as Phrasing), 1 + between.length, {
        ...target,
        children: mergeAdjacent([
          ...(target.children as Phrasing[]),
          ...between,
          ...((node as Mdast.Parent).children as Phrasing[]),
        ]),
      } as Phrasing);
    } else {
      merged.push(node);
    }
  }

  return merged;
}

function inlineToPhrasing(node: LexicalNode): Phrasing[] {
  if ($isLineBreakNode(node)) return [{ type: "break" }];
  if ($isTextNode(node)) return [textToPhrasing(node)];
  if ($isElementNode(node)) return childrenToPhrasing(node);
  return [];
}

function childrenToPhrasing(node: ElementNode): Phrasing[] {
  return mergeAdjacent(node.getChildren().flatMap(inlineToPhrasing));
}

function hasContent(phrasing: Phrasing[]): boolean {
  return phrasing.some((node) => node.type !== "break");
}

function listToMdast(list: ListNode): Mdast.List {
  const items: Mdast.ListItem[] = [];

  for (const item of list.getChildren()) {
    if (!$isListItemNode(item)) continue;

    const children = item.getChildren();
    const nestedLists = children.filter($isListNode).map(listToMdast);
    const phrasing = mergeAdjacent(
      children.filter((child) => !$isListNode(child)).flatMap(inlineToPhrasing),
    );

    // A list item holding only a nested list continues the item before it
    const previous = items[items.length - 1];
    if (phrasing.length === 0 && nestedLists.length > 0 && previous) {
      previous.children.push(...nestedLists);
      continue;
    }

    items.push({
      type: "listItem",
      spread: false,
      children: [
        ...(phrasing.length > 0
          ? [{ type: "paragraph", children: phrasing } as Mdast.Paragraph]
          : []),
        ...nestedLists,
      ],
    });
  }

  const ordered = list.getListType() === "number";
  return {
    type: "list",
    ordered,
    start: ordered ? list.getStart() : undefined,
    spread: false,
    children: items,
  };
}

function blockToMdast(node: LexicalNode): Mdast.RootContent | null {
  if ($isListNode(node)) return listToMdast(node);
  if (!$isElementNode(node)) return null;

  const phrasing = childrenToPhrasing(node);
  if (!hasContent(phrasing)) return null;

  if ($isQuoteNode(node)) {
    return {
      type: "blockquote",
      children: [{ type: "paragraph", children: phrasing }],
    };
  }
  return { type: "paragraph", children: phrasing };
}

function wrapperHandle(open: string, close: string): Handle {
  return (node, _parent, state, info) => {
    const tracker = state.createTracker(info);
    let value = tracker.move(open);
    value += tracker.move(
      state.containerPhrasing(node, {
        before: value,
        after: close.charAt(0),
        ...tracker.current(),
      }),
    );
    value += tracker.move(close);
    return value;
  };
}

const TO_MARKDOWN_OPTIONS: ToMarkdownOptions = {
  // Only strikethrough: the rest of GFM would escape bare URLs, which MarkdownContent should still link
  extensions: [gfmStrikethroughToMarkdown()],
  bullet: "-",
  emphasis: "*",
  strong: "*",
  listItemIndent: "one",
  handlers: {
    // MarkdownContent renders with remark-breaks, so a plain newline is a line break (rather than "\" + newline)
    break: () => "\n",
    underline: wrapperHandle("<u>", "</u>"),
    spoiler: wrapperHandle(">!", "!<"),
  },
  unsafe: [
    // Typed text must never read as a spoiler (MarkdownContent finds >!...!< before parsing, ignoring escapes)
    { character: "!", before: ">" },
    { character: "<", before: "!" },
  ],
};

export function $convertToMarkdownString(): string {
  const children = $getRoot()
    .getChildren()
    .map(blockToMdast)
    .filter((block): block is Mdast.RootContent => block !== null);

  return toMarkdown({ type: "root", children }, TO_MARKDOWN_OPTIONS).trim();
}
