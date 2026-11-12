// How deep a thread nests before it continues in its own view, as Reddit's does: the comment at this depth (0 is
// top-level) shows "N more replies", which opens its replies on their own, instead of nesting them. Decided by the
// widget's own width, not the screen's, since it also sits in narrow places on wide screens (side panels, sidebars,
// embeds): replies nest only while the deepest one still has room for its text, so a narrow widget gets fewer levels
// rather than squashed ones.

// The narrowest text column a reply gets: about 40 characters a line
const MIN_TEXT_WIDTH = 280;
// The avatar's column beside each comment's text
const AVATAR_COLUMN = 44;
// Always this many levels (three), however narrow; at most eight
const MIN_DEPTH = 2;
const MAX_DEPTH = 7;

// How far in a comment at each depth starts: CommentCard's getReplyIndentClass, added up. 32px a level, except that
// phones stop indenting after the fourth (a media query, so on the window's width: an embed's own frame).
function indentAt(depth: number, isSmall: boolean): number {
  let indent = 0;
  for (let level = 1; level <= depth; level++) {
    if (!isSmall || level <= 4) indent += 32;
  }
  return indent;
}

export function continueDepthFor(widgetWidth: number): number {
  const isSmall =
    typeof window !== "undefined" &&
    !window.matchMedia("(min-width: 640px)").matches;

  let depth = MIN_DEPTH;
  while (depth < MAX_DEPTH) {
    const indent = indentAt(depth + 1, isSmall);
    // Where phones stop indenting, nesting would only be a flat chain
    if (indent === indentAt(depth, isSmall)) break;
    if (widgetWidth - AVATAR_COLUMN - indent < MIN_TEXT_WIDTH) break;
    depth++;
  }
  return depth;
}
