import { $isLinkNode, $createLinkNode, LinkNode } from "@lexical/link";
import {
  $isListItemNode,
  $isListNode,
  $createListNode,
  $createListItemNode,
  ListNode,
} from "@lexical/list";
import {
  $isHeadingNode,
  $isQuoteNode,
  $createHeadingNode,
  $createQuoteNode,
  HeadingTagType,
} from "@lexical/rich-text";
import {
  $createLineBreakNode,
  $createParagraphNode,
  $createTextNode,
  $getRoot,
  $isElementNode,
  $isLineBreakNode,
  $isParagraphNode,
  $isTextNode,
  ElementNode,
  LexicalNode,
  ParagraphNode,
  TextFormatType,
  TextNode,
} from "lexical";

// --- Serialize: Lexical -> markdown ---

function escapePlainText(text: string): string {
  return text.replace(/([\\*~`<>[\]])/g, "\\$1");
}

function serializeTextNode(node: TextNode): string {
  let text = escapePlainText(node.getTextContent());
  if (node.hasFormat("code")) text = `\`${text}\``;
  if (node.hasFormat("bold")) text = `**${text}**`;
  if (node.hasFormat("italic")) text = `*${text}*`;
  if (node.hasFormat("strikethrough")) text = `~~${text}~~`;
  if (node.hasFormat("underline")) text = `<u>${text}</u>`;
  if (node.hasFormat("highlight")) text = `>!${text}!<`;
  return text;
}

function serializeInlineNode(node: LexicalNode): string {
  if ($isLineBreakNode(node)) return "\n";
  if ($isLinkNode(node)) {
    const inner = (node as LinkNode)
      .getChildren()
      .map(serializeInlineNode)
      .join("");
    return `[${inner}](${(node as LinkNode).getURL()})`;
  }
  if ($isTextNode(node)) return serializeTextNode(node);
  if ($isElementNode(node)) {
    return node.getChildren().map(serializeInlineNode).join("");
  }
  return "";
}

function serializeInlineChildren(node: ElementNode): string {
  return node.getChildren().map(serializeInlineNode).join("");
}

function serializeList(listNode: ListNode, depth: number): string {
  const ordered = listNode.getListType() === "number";
  const indent = "  ".repeat(depth);

  return listNode
    .getChildren()
    .map((item, index) => {
      const marker = ordered ? `${index + 1}. ` : "- ";
      const nestedLists: string[] = [];
      const inlineParts: string[] = [];

      if ($isListItemNode(item)) {
        item.getChildren().forEach((child) => {
          if ($isListNode(child)) {
            nestedLists.push(serializeList(child, depth + 1));
          } else {
            inlineParts.push(serializeInlineNode(child));
          }
        });
      }

      let line = `${indent}${marker}${inlineParts.join("")}`;
      if (nestedLists.length > 0) line += `\n${nestedLists.join("\n")}`;
      return line;
    })
    .join("\n");
}

function serializeBlock(node: LexicalNode): string {
  if ($isHeadingNode(node)) {
    const level = Number(node.getTag().slice(1)) || 1;
    return `${"#".repeat(level)} ${serializeInlineChildren(node)}`;
  }
  if ($isQuoteNode(node)) {
    return serializeInlineChildren(node)
      .split("\n")
      .map((line) => `> ${line}`)
      .join("\n");
  }
  if ($isListNode(node)) return serializeList(node, 0);
  if ($isParagraphNode(node)) return serializeInlineChildren(node);
  if ($isElementNode(node)) return serializeInlineChildren(node);
  return "";
}

export function $convertToMarkdownString(): string {
  return $getRoot()
    .getChildren()
    .map(serializeBlock)
    .filter((block) => block.length > 0)
    .join("\n\n");
}

// --- Parse: markdown -> Lexical ---

type InlineRule = { regex: RegExp; format: TextFormatType };

const INLINE_RULES: InlineRule[] = [
  { regex: /\*\*([^*]+)\*\*/, format: "bold" },
  { regex: /~~([^~]+)~~/, format: "strikethrough" },
  { regex: /<u>([\s\S]+?)<\/u>/, format: "underline" },
  { regex: />!([\s\S]+?)!</, format: "highlight" },
  { regex: /`([^`]+)`/, format: "code" },
  { regex: /\*([^*]+)\*/, format: "italic" },
];

const LINK_RULE = /\[([^\]]+)\]\(([^)\s]+)\)/;

function unescapePlainText(text: string): string {
  return text.replace(/\\([\\*~`<>[\]])/g, "$1");
}

function findEarliestMatch(text: string): {
  index: number;
  length: number;
  inner: string;
  format?: TextFormatType;
  isLink?: boolean;
  url?: string;
} | null {
  let best: ReturnType<typeof findEarliestMatch> = null;

  for (const rule of INLINE_RULES) {
    const match = rule.regex.exec(text);
    if (match && (best === null || match.index < best.index)) {
      best = {
        index: match.index,
        length: match[0].length,
        inner: match[1],
        format: rule.format,
      };
    }
  }

  const linkMatch = LINK_RULE.exec(text);
  if (linkMatch && (best === null || linkMatch.index < best.index)) {
    best = {
      index: linkMatch.index,
      length: linkMatch[0].length,
      inner: linkMatch[1],
      isLink: true,
      url: linkMatch[2],
    };
  }

  return best;
}

function parseInline(
  text: string,
  activeFormats: ReadonlySet<TextFormatType>,
): LexicalNode[] {
  if (text.length === 0) return [];

  const match = findEarliestMatch(text);

  if (!match) {
    const textNode = $createTextNode(unescapePlainText(text));
    activeFormats.forEach((format) => textNode.toggleFormat(format));
    return [textNode];
  }

  const before = text.slice(0, match.index);
  const after = text.slice(match.index + match.length);

  const nodes: LexicalNode[] = [];
  nodes.push(...parseInline(before, activeFormats));

  if (match.isLink && match.url) {
    const link = $createLinkNode(match.url);
    parseInline(match.inner, activeFormats).forEach((child) =>
      link.append(child),
    );
    nodes.push(link);
  } else if (match.format) {
    const nextFormats = new Set(activeFormats);
    nextFormats.add(match.format);
    nodes.push(...parseInline(match.inner, nextFormats));
  }

  nodes.push(...parseInline(after, activeFormats));
  return nodes;
}

function appendInlineFromLines(target: ElementNode, lines: string[]): void {
  lines.forEach((line, index) => {
    if (index > 0) target.append($createLineBreakNode());
    parseInline(line, new Set()).forEach((node) => target.append(node));
  });
}

function leadingSpaces(line: string): number {
  const match = /^(\s*)/.exec(line);
  return match ? match[1].length : 0;
}

const LIST_ITEM_RE = /^\s*(?:[-*]|\d+\.)\s+(.*)$/;

function isListBlock(lines: string[]): boolean {
  return lines.every((line) => line.trim().length === 0 || LIST_ITEM_RE.test(line));
}

function parseList(lines: string[]): ListNode {
  const ordered = /^\s*\d+\.\s/.test(lines[0] ?? "");
  const list = $createListNode(ordered ? "number" : "bullet");

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const match = LIST_ITEM_RE.exec(line);
    if (!match) {
      i += 1;
      continue;
    }

    const item = $createListItemNode();
    appendInlineFromLines(item, [match[1]]);

    let j = i + 1;
    const childLines: string[] = [];
    while (j < lines.length && leadingSpaces(lines[j]) >= 2) {
      childLines.push(lines[j].slice(2));
      j += 1;
    }
    if (childLines.length > 0) item.append(parseList(childLines));

    list.append(item);
    i = j;
  }

  return list;
}

function parseBlock(block: string): LexicalNode {
  const lines = block.split("\n");

  const headingMatch = /^(#{1,6})\s+(.*)$/.exec(lines[0]);
  if (headingMatch && lines.length === 1) {
    const heading = $createHeadingNode(
      `h${headingMatch[1].length}` as HeadingTagType,
    );
    appendInlineFromLines(heading, [headingMatch[2]]);
    return heading;
  }

  if (lines.every((line) => line.startsWith("> "))) {
    const quote = $createQuoteNode();
    appendInlineFromLines(
      quote,
      lines.map((line) => line.slice(2)),
    );
    return quote;
  }

  if (isListBlock(lines)) {
    return parseList(lines);
  }

  const paragraph = $createParagraphNode() as ParagraphNode;
  appendInlineFromLines(paragraph, lines);
  return paragraph;
}

export function $convertFromMarkdownString(markdown: string): void {
  const root = $getRoot();
  root.clear();

  const blocks = markdown.split(/\n\s*\n/).filter((block) => block.trim().length > 0);

  if (blocks.length === 0) {
    root.append($createParagraphNode());
    return;
  }

  blocks.forEach((block) => root.append(parseBlock(block)));
}
