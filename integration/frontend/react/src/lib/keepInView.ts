const HOLD_MS = 30_000;

// What a viewer might scroll with, the scrollbar (mousedown) and the keyboard included
const INPUTS = ["wheel", "touchmove", "mousedown", "keydown"] as const;

/**
 * Scrolls to an element and keeps it there while the page around it settles: whatever the host loads above the widget,
 * and the images in the comments above, would otherwise push it away. Ends as soon as the viewer does anything, or after
 * a while. Returns a way to end it.
 */
export function keepInView(
  element: Element,
  block: ScrollLogicalPosition,
): () => void {
  // In a frame, scrolling moves the page around it too, whose viewer's input isn't seen here: once only
  if (window.parent !== window) {
    element.scrollIntoView({ block });
    return () => {};
  }

  const root = document.documentElement;
  // Scrolling by itself to make up for what loads above, browsers would do part of the job, from another element
  root.style.overflowAnchor = "none";

  const align = () => {
    if (element.isConnected)
      element.scrollIntoView({ block, behavior: "instant" });
    else stop();
  };
  // Runs after layout and before the page paints, so nothing is seen to move
  const observer = new ResizeObserver(align);
  const stop = () => {
    observer.disconnect();
    clearTimeout(timeout);
    for (const type of INPUTS) window.removeEventListener(type, stop);
    root.style.overflowAnchor = "";
  };
  const timeout = setTimeout(stop, HOLD_MS);
  for (const type of INPUTS)
    window.addEventListener(type, stop, { passive: true });

  align();
  observer.observe(document.body);
  return stop;
}
