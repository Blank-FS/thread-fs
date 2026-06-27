export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function preprocessRedditMarkdown(markdown: string): string {
  return markdown.replace(/>!([^]*?)!</g, (_match, content: string) => {
    return `<span class="threadfs-spoiler">${escapeHtml(content)}</span>`;
  });
}

export function markdownToPlainText(markdown: string): string {
  return markdown
    .replace(/>!([^]*?)!</g, "$1")
    .replace(/<u>([^]*?)<\/u>/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[#>*_~`\[\]()!-]/g, "")
    .trim();
}
