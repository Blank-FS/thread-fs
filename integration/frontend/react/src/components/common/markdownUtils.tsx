export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// One span per paragraph: a span can't cross a paragraph break, so a spoiler over several would come apart
export function preprocessRedditMarkdown(markdown: string): string {
  return markdown.replace(/>!([^]*?)!</g, (_match, content: string) =>
    content
      .split(/\n\s*\n/)
      .map(
        (part) => `<span class="threadfs-spoiler">${escapeHtml(part)}</span>`,
      )
      .join("\n\n"),
  );
}

export function markdownToPlainText(markdown: string): string {
  return markdown
    .replace(/>!([^]*?)!</g, "$1")
    .replace(/<u>([^]*?)<\/u>/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[#>*_~`\[\]()!-]/g, "")
    .trim();
}
