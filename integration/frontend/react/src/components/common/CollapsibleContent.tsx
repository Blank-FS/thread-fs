import { ChevronDown, ChevronUp } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { cn } from "../../lib/utils";

type CollapsibleContentProps = {
  maxHeight?: number;
  children: React.ReactNode;
  className?: string;
};

export function CollapsibleContent({
  maxHeight = 320,
  children,
  className,
}: CollapsibleContentProps) {
  const contentRef = useRef<HTMLDivElement | null>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  useLayoutEffect(() => {
    const element = contentRef.current;
    if (!element) return;

    const checkOverflow = () => {
      setIsOverflowing(element.scrollHeight > maxHeight + 1);
    };

    checkOverflow();

    const observer = new ResizeObserver(checkOverflow);
    observer.observe(element);

    return () => observer.disconnect();
  }, [maxHeight, children]);

  const isClamped = isOverflowing && !isExpanded;

  return (
    <div className={cn("relative", className)}>
      <div
        ref={contentRef}
        style={isClamped ? { maxHeight, overflow: "hidden" } : undefined}
      >
        {children}
      </div>

      {isClamped && (
        <div className="from-background pointer-events-none absolute inset-x-0 bottom-8 h-12 bg-gradient-to-t to-transparent" />
      )}

      {isOverflowing && (
        <button
          type="button"
          onClick={() => setIsExpanded((value) => !value)}
          className="text-muted-foreground hover:bg-primary/10 mt-1 inline-flex items-center gap-1 rounded-full px-2 py-1 text-sm font-medium hover:cursor-pointer hover:underline"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="size-4" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="size-4" />
              Show more
            </>
          )}
        </button>
      )}
    </div>
  );
}
