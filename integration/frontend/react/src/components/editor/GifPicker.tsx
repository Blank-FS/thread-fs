import {
  attachmentOf,
  registerGifShare,
  searchGifs,
  thumbnailOf,
  type KlipyItem,
} from "@/lib/gifs";
import type { ThreadFSGif, ThreadFSGifConfig } from "@/lib/types";
import { Search, X } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

type GifPickerProps = {
  config: ThreadFSGifConfig;
  onPick: (gif: ThreadFSGif) => void;
  onClose: () => void;
};

const SEARCH_DELAY_MS = 350;

/**
 * GIF search, in a popover under the comment box's GIF button. Trending GIFs until something's typed. Results stay in
 * KLIPY's order, as their terms ask.
 */
export default function GifPicker({ config, onPick, onClose }: GifPickerProps) {
  const [query, setQuery] = useState("");
  const [searchedQuery, setSearchedQuery] = useState("");
  const [items, setItems] = useState<KlipyItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // A new search starts over at page one, after a pause in typing
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(
      () => {
        setIsLoading(true);
        setError(null);
        searchGifs(config, query, 1, controller.signal)
          .then((result) => {
            setItems(result.items);
            setHasNext(result.hasNext);
            setPage(1);
            setSearchedQuery(query);
          })
          .catch((err: unknown) => {
            if (controller.signal.aborted) return;
            setItems([]);
            setHasNext(false);
            setError(err instanceof Error ? err.message : "GIF search failed");
          })
          .finally(() => {
            if (!controller.signal.aborted) setIsLoading(false);
          });
      },
      query ? SEARCH_DELAY_MS : 0,
    );

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [config, query]);

  async function loadMore() {
    if (isLoading || !hasNext) return;
    setIsLoading(true);
    try {
      const result = await searchGifs(config, searchedQuery, page + 1);
      setItems((current) => [...current, ...result.items]);
      setHasNext(result.hasNext);
      setPage(page + 1);
    } catch {
      setHasNext(false);
    } finally {
      setIsLoading(false);
    }
  }

  function pick(item: KlipyItem) {
    const gif = attachmentOf(item);
    if (!gif) return;
    registerGifShare(config, item.slug, searchedQuery);
    onPick(gif);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    onClose();
  }

  return (
    <div
      onKeyDown={handleKeyDown}
      className="@container flex min-h-0 flex-col"
    >
      <div className="flex items-center gap-1 border-b px-2">
        <Search className="text-muted-foreground size-4 shrink-0" />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          // KLIPY's terms ask for this wording
          placeholder="Search KLIPY"
          aria-label="Search GIFs"
          className="min-w-0 flex-1 bg-transparent py-1.5 text-sm focus:outline-none"
        />
        <button
          type="button"
          onClick={onClose}
          aria-label="Close GIFs"
          title="Close"
          className="text-muted-foreground hover:bg-primary/20 flex size-6 shrink-0 items-center justify-center rounded-md hover:cursor-pointer"
        >
          <X className="size-4" />
        </button>
      </div>

      <div
        // The results scroll, up to their usual height, in whatever room the popover has; the search and the
        // attribution stay put
        className="max-h-72 min-h-0 flex-1 overflow-y-auto p-1"
        onScroll={(event) => {
          const el = event.currentTarget;
          if (el.scrollHeight - el.scrollTop - el.clientHeight < 120) {
            void loadMore();
          }
        }}
      >
        {error ? (
          <p className="text-muted-foreground p-3 text-center text-sm">
            {error}
          </p>
        ) : !isLoading && items.length === 0 ? (
          <p className="text-muted-foreground p-3 text-center text-sm">
            No GIFs found
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-1 @[22rem]:grid-cols-3">
            {items.map((item) => {
              const thumbnail = thumbnailOf(item);
              if (!thumbnail) return null;
              return (
                <button
                  key={`${item.id}-${item.slug}`}
                  type="button"
                  onClick={() => pick(item)}
                  aria-label={item.title || "GIF"}
                  title={item.title || undefined}
                  className="bg-muted focus-visible:ring-ring h-24 overflow-hidden rounded-md hover:cursor-pointer hover:opacity-80 focus-visible:ring-2 focus-visible:outline-none"
                  style={
                    item.blur_preview
                      ? {
                          backgroundImage: `url("${item.blur_preview}")`,
                          backgroundSize: "cover",
                        }
                      : undefined
                  }
                >
                  <img
                    src={thumbnail.url}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    referrerPolicy="no-referrer"
                    className="size-full object-cover"
                  />
                </button>
              );
            })}
            {isLoading &&
              Array.from({ length: items.length ? 3 : 6 }, (_, i) => (
                <div
                  key={`loading-${i}`}
                  className="bg-muted h-24 animate-pulse rounded-md"
                />
              ))}
          </div>
        )}
      </div>

      <p className="text-muted-foreground border-t px-2 py-1 text-right text-[10px]">
        Powered by KLIPY
      </p>
    </div>
  );
}
