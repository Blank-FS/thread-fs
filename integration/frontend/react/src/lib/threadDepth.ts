// How deep a thread nests before it continues in its own view, as Reddit's does ("Continue this thread"): the comment
// at this depth (0 is top-level) shows a link to its replies instead of nesting them. Decided by the widget's own width,
// not the screen's, since it also sits in narrow places on wide screens (side panels, sidebars, embeds).

const NARROW_WIDTH = 640; // Tailwind's sm breakpoint

export function continueDepthFor(widgetWidth: number): number {
  // Phones and narrow columns: four levels. Wider: eight, which still leaves a comfortable column for the text.
  return widgetWidth < NARROW_WIDTH ? 3 : 7;
}
