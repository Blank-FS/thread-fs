import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react";

// Clickjacking: a widget in a frame that other sites can embed may be covered, made transparent or clipped by the page
// around it, so a viewer's click lands on a vote they never saw. Chromium's IntersectionObserver can say whether an
// element is really visible (trackVisibility). It's cautious: a sticky header over any part of a frame from another
// site makes everything in that frame count as hidden, so "hidden" means unproven, and the host decides (confirmClick).

/** What a guarded click would do, for the host to say. */
export type ThreadFSClickAction = {
  kind: "vote" | "report" | "post";
  /** A vote's outcome: 0 takes it back. */
  value?: 1 | -1 | 0;
  /** Whose comment it's on. */
  authorName?: string | null;
  /** The controls were mostly outside the window, as in a frame cropped to one button. */
  isClipped: boolean;
};

/** True goes ahead and false doesn't, with a notice; null doesn't either, quietly (the viewer took it back). */
export type ConfirmClick = (
  action: ThreadFSClickAction,
) => Promise<boolean | null>;

/** How long a control must have been visible before a click on it counts: an overlay lifted just in time doesn't pass. */
const VISIBLE_FOR_MS = 600;
/** And still be visible this long after, for a page that hides it as the click lands. Reports come every 100ms. */
const SETTLE_MS = 150;
/** How much of the controls must be inside the viewport, so a frame cropped to one button doesn't pass. */
const VISIBLE_PART = 0.5;

type VisibilityEntry = IntersectionObserverEntry & { isVisible?: boolean };

const canTrackVisibility = () =>
  typeof IntersectionObserverEntry !== "undefined" &&
  "isVisible" in IntersectionObserverEntry.prototype;

class ClickGuard {
  // Each group of guarded controls, and since when it's been visible (null: it isn't)
  private visibleSince = new Map<Element, number | null>();
  private clipped = new Set<Element>();
  private observer: IntersectionObserver | null = null;
  private lastClicked: Element | null = null;

  start() {
    const tracks = canTrackVisibility();
    this.observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries as VisibilityEntry[]) {
          const clipped = entry.intersectionRatio < VISIBLE_PART;
          if (clipped) this.clipped.add(entry.target);
          else this.clipped.delete(entry.target);

          const visible = entry.isVisible === true && !clipped;
          const since = this.visibleSince.get(entry.target);
          if (visible && since == null)
            this.visibleSince.set(entry.target, performance.now());
          if (!visible) this.visibleSince.set(entry.target, null);
        }
      },
      {
        threshold: [0, 0.25, VISIBLE_PART, 0.75, 1],
        ...(tracks && { trackVisibility: true, delay: 100 }),
      } as IntersectionObserverInit,
    );
    for (const element of this.visibleSince.keys())
      this.observer.observe(element);
    document.addEventListener("click", this.onClick, true);
  }

  stop() {
    document.removeEventListener("click", this.onClick, true);
    this.observer?.disconnect();
    this.observer = null;
    for (const element of this.visibleSince.keys())
      this.visibleSince.set(element, null);
  }

  watch(element: Element) {
    this.visibleSince.set(element, null);
    this.observer?.observe(element);
  }

  unwatch(element: Element) {
    this.visibleSince.delete(element);
    this.clipped.delete(element);
    this.observer?.unobserve(element);
  }

  private onClick = (event: Event) => {
    this.lastClicked = event.target instanceof Element ? event.target : null;
  };

  /** The guarded controls the last click was on. */
  private clickedControls(): Element | null {
    for (const element of this.visibleSince.keys())
      if (this.lastClicked && element.contains(this.lastClicked))
        return element;
    return null;
  }

  /**
   * Whether the last click may go ahead. `confirm` is called in the click itself when the controls weren't visible or
   * the browser can't say, so it may open a popup.
   */
  allow(
    action: Omit<ThreadFSClickAction, "isClipped">,
    confirm: ConfirmClick,
  ): Promise<boolean | null> {
    const controls = this.clickedControls();
    const since = controls && this.visibleSince.get(controls);
    const ask = () =>
      confirm({
        ...action,
        isClipped: controls !== null && this.clipped.has(controls),
      });
    if (
      !controls ||
      since == null ||
      performance.now() - since < VISIBLE_FOR_MS
    )
      return ask();
    return new Promise((resolve) => setTimeout(resolve, SETTLE_MS)).then(() =>
      // Gone since (a menu closes as its item is picked) is as good as visible; hidden isn't
      !this.visibleSince.has(controls) ||
      this.visibleSince.get(controls) === since
        ? true
        : ask(),
    );
  }
}

const ClickGuardContext = createContext<ClickGuard | null>(null);
export const ClickGuardProvider = ClickGuardContext.Provider;

/**
 * The guard for a widget, and a check to make before acting on a click. Without `confirm` there's no guard, and every
 * click goes ahead.
 */
export function useClickGuard(confirm: ConfirmClick | undefined) {
  const enabled = Boolean(confirm);
  const guard = useMemo(() => (enabled ? new ClickGuard() : null), [enabled]);
  const confirmRef = useRef(confirm);
  useEffect(() => {
    confirmRef.current = confirm;
  });
  useEffect(() => {
    guard?.start();
    return () => guard?.stop();
  }, [guard]);

  const allowClick = useCallback(
    (
      action: Omit<ThreadFSClickAction, "isClipped">,
    ): Promise<boolean | null> =>
      guard
        ? guard.allow(
            action,
            (full) => confirmRef.current?.(full) ?? Promise.resolve(true),
          )
        : Promise.resolve(true),
    [guard],
  );
  return { guard, allowClick };
}

/** A ref for an element holding guarded controls. It mustn't have opacity or filters of its own, nor its ancestors. */
export function useGuardedControls() {
  const guard = useContext(ClickGuardContext);
  const current = useRef<Element | null>(null);
  return useCallback(
    (element: HTMLElement | null) => {
      if (current.current) guard?.unwatch(current.current);
      current.current = element;
      if (element) guard?.watch(element);
    },
    [guard],
  );
}
