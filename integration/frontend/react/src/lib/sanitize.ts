import DOMPurify from "dompurify";

function removeTrailingEmptyBlocks(html: string): string {
  if (typeof window === "undefined") {
    return html;
  }

  const template = document.createElement("template");
  template.innerHTML = html;

  function isEmptyBlock(element: Element): boolean {
    const tag = element.tagName.toLowerCase();

    if (!["p", "div"].includes(tag)) {
      return false;
    }

    const text = element.textContent?.replace(/\u00a0/g, " ").trim() ?? "";

    const hasOnlyBreaksOrWhitespace = Array.from(element.childNodes).every(
      (node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          return (node.textContent ?? "").replace(/\u00a0/g, " ").trim() === "";
        }

        if (node.nodeType === Node.ELEMENT_NODE) {
          const child = node as Element;
          return child.tagName.toLowerCase() === "br";
        }

        return false;
      },
    );

    return text.length === 0 && hasOnlyBreaksOrWhitespace;
  }

  while (
    template.content.lastElementChild &&
    isEmptyBlock(template.content.lastElementChild)
  ) {
    template.content.lastElementChild.remove();
  }

  return template.innerHTML;
}

export function sanitizeCommentHtml(html: string): string {
  const withoutTrailingEmptyBlocks = removeTrailingEmptyBlocks(html);

  const sanitized = DOMPurify.sanitize(withoutTrailingEmptyBlocks, {
    ALLOWED_TAGS: [
      "p",
      "br",
      "strong",
      "b",
      "em",
      "i",
      "u",
      "s",
      "blockquote",
      "code",
      "pre",
      "ul",
      "ol",
      "li",
      "a",
    ],
    ALLOWED_ATTR: ["href", "title", "target", "rel"],
    ALLOW_DATA_ATTR: false,
  });

  return removeTrailingEmptyBlocks(sanitized);
}
