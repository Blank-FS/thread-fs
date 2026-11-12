import { createContext, useContext } from "react";
import type { ThreadFSGif, ThreadFSGifConfig } from "./types";

// GIFs from KLIPY (https://docs.klipy.com). Their terms have the reader's browser search with the community's app key,
// with no server in between, and show results as they come: in their order, from their URLs, unchanged. No customer
// id is sent, so nothing identifies the reader to KLIPY beyond the request itself (and no ads, which need one).

// The community's GIF search, for every comment box in the widget. Null when it's off.
export const GifConfigContext = createContext<ThreadFSGifConfig | null>(null);

export const useGifConfig = () => useContext(GifConfigContext);

const KLIPY_API = "https://api.klipy.com/api/v1";

type KlipyFile = { url: string; width: number; height: number; size?: number };
type KlipySize = Partial<Record<"gif" | "webp" | "jpg" | "mp4" | "webm", KlipyFile>>;

export type KlipyItem = {
  id: number;
  slug: string;
  title?: string;
  type?: string;
  blur_preview?: string;
  file?: Partial<Record<"hd" | "md" | "sm" | "xs", KlipySize>>;
};

export type KlipyPage = {
  items: KlipyItem[];
  hasNext: boolean;
};

const PER_PAGE = 24;

/** Trending GIFs for an empty search, else the search's results, a page at a time. */
export async function searchGifs(
  config: ThreadFSGifConfig,
  query: string,
  page: number,
  signal?: AbortSignal,
): Promise<KlipyPage> {
  const q = query.trim();
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(PER_PAGE),
  });
  if (q) params.set("q", q);

  const res = await fetch(
    `${KLIPY_API}/${encodeURIComponent(config.app_key)}/gifs/${q ? "search" : "trending"}?${params}`,
    { signal },
  );
  if (!res.ok) {
    // KLIPY answers an unknown or inactive key with an error: worth telling the reader it's not their search
    throw new Error(
      res.status === 401 || res.status === 403 || res.status === 404
        ? `GIF search isn't set up right (KLIPY said ${res.status})`
        : `GIF search failed (${res.status})`,
    );
  }

  // { result, data: { data: [...items], current_page, per_page, has_next } }
  const body = await res.json();
  const items = body?.data?.data ?? body?.data;
  return {
    items: Array.isArray(items) ? items : [],
    hasNext: Boolean(body?.data?.has_next),
  };
}

/** Tells KLIPY a GIF was picked, which improves its results (their share trigger). Best effort. */
export function registerGifShare(
  config: ThreadFSGifConfig,
  slug: string,
  query: string,
) {
  void fetch(
    `${KLIPY_API}/${encodeURIComponent(config.app_key)}/gifs/share/${encodeURIComponent(slug)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q: query.trim() }),
      keepalive: true,
    },
  ).catch(() => {});
}

// Animated WebP is far smaller than GIF; GIF where there's no WebP
function pickFile(item: KlipyItem, sizes: ("hd" | "md" | "sm" | "xs")[]) {
  for (const size of sizes) {
    const file = item.file?.[size]?.webp ?? item.file?.[size]?.gif;
    if (file?.url && file.width > 0 && file.height > 0) return file;
  }
  return null;
}

/** The small file for the picker's grid. */
export function thumbnailOf(item: KlipyItem) {
  return pickFile(item, ["sm", "xs", "md"]);
}

/** What a comment keeps: a file sized for showing under the text. */
export function attachmentOf(item: KlipyItem): ThreadFSGif | null {
  const file = pickFile(item, ["md", "sm", "hd"]);
  if (!file) return null;
  return {
    provider: "klipy",
    slug: item.slug,
    url: file.url,
    width: file.width,
    height: file.height,
    title: item.title?.slice(0, 255) || null,
  };
}
