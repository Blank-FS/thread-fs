import { isAllowedImage } from "@/lib/imageHosts";
import type { ThreadFSImage } from "@/lib/types";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "../ui/button";

type ImageLinkFormProps = {
  /** The community's image hosts: the only sites an image can come from. */
  hosts: readonly string[];
  onAdd: (image: ThreadFSImage) => void;
  onCancel: () => void;
};

type Preview =
  | { state: "empty" }
  | { state: "unsupported"; host: string | null }
  | { state: "loading" }
  | { state: "broken" }
  | { state: "ready"; width: number; height: number };

/**
 * "Add image": a link to an image on one of the community's image hosts, as there are no uploads. It shows the image
 * before it's added, and says why when it can't be: a site that isn't on the list (which is never loaded), or a link
 * that isn't an image.
 */
export default function ImageLinkForm({
  hosts,
  onAdd,
  onCancel,
}: ImageLinkFormProps) {
  const [url, setUrl] = useState("");
  const [loaded, setLoaded] = useState<{
    url: string;
    width: number;
    height: number;
  } | null>(null);
  const [brokenUrl, setBrokenUrl] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const trimmed = url.trim();
  const preview: Preview = (() => {
    if (!trimmed) return { state: "empty" };
    if (!isAllowedImage(trimmed, hosts)) {
      let host: string | null = null;
      try {
        host = new URL(trimmed).hostname || null;
      } catch {
        host = null;
      }
      return { state: "unsupported", host };
    }
    if (brokenUrl === trimmed) return { state: "broken" };
    if (loaded?.url === trimmed) {
      return { state: "ready", width: loaded.width, height: loaded.height };
    }
    return { state: "loading" };
  })();

  function add(event: FormEvent) {
    event.preventDefault();
    if (preview.state !== "ready") return;
    onAdd({ url: trimmed, width: preview.width, height: preview.height });
  }

  return (
    <form onSubmit={add} className="space-y-3 p-3">
      <div className="space-y-1">
        <p className="text-sm font-semibold">Add image</p>
        <p className="text-muted-foreground text-xs">
          Supported sites:
        </p>
        <ul className="flex flex-wrap gap-1">
          {hosts.map((host) => (
            <li
              key={host}
              className="bg-muted rounded px-1.5 py-0.5 font-mono text-[11px]"
            >
              {host}
            </li>
          ))}
        </ul>
      </div>

      <input
        ref={inputRef}
        type="url"
        inputMode="url"
        value={url}
        onChange={(event) => setUrl(event.target.value)}
        placeholder={`https://${hosts[0] ?? "example.com"}/...`}
        aria-label="Image link"
        className="border-input dark:bg-input/30 focus-visible:border-ring focus-visible:ring-ring/50 h-8 w-full rounded-lg border bg-transparent px-2.5 text-sm outline-none focus-visible:ring-3"
      />

      {/* The preview, or why there isn't one. An image from a site that isn't on the list is never loaded */}
      {preview.state !== "empty" && (
        <div className="bg-muted/50 flex min-h-24 items-center justify-center overflow-hidden rounded-lg border">
          {preview.state === "unsupported" ? (
            <p className="text-muted-foreground p-3 text-center text-xs">
              {unsupportedMessage(preview.host, hosts)}
            </p>
          ) : preview.state === "broken" ? (
            <p className="text-muted-foreground p-3 text-center text-xs">
              Couldn&apos;t load an image from that link. Make sure it&apos;s
              the image itself, not the page it&apos;s on.
            </p>
          ) : (
            <img
              key={trimmed}
              src={trimmed}
              alt=""
              referrerPolicy="no-referrer"
              onLoad={(event) => {
                const img = event.currentTarget;
                if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                  setLoaded({
                    url: trimmed,
                    width: img.naturalWidth,
                    height: img.naturalHeight,
                  });
                } else {
                  setBrokenUrl(trimmed);
                }
              }}
              onError={() => setBrokenUrl(trimmed)}
              className="max-h-40 max-w-full object-contain"
            />
          )}
        </div>
      )}

      <div className="flex justify-end gap-1">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="px-2 hover:cursor-pointer"
          onClick={onCancel}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          disabled={preview.state !== "ready"}
          className="px-2 hover:cursor-pointer"
        >
          Add
        </Button>
      </div>
    </form>
  );
}

// Why a link can't be added. A page on one of the sites (imgur.com/abc, where the image is on i.imgur.com) is the
// usual mistake, so that gets told how to find the image's own address
function unsupportedMessage(host: string | null, hosts: readonly string[]) {
  if (!host) return "That isn't a link to an image.";
  const isPageOnASite = hosts.some(
    (allowed) => allowed.endsWith(`.${host}`) || host.endsWith(`.${allowed}`),
  );
  if (isPageOnASite) {
    return "That's the page the image is on. Use the image's own address: right-click the image and copy the image address.";
  }
  return `${host} isn't one of the sites above, so its images can't be added.`;
}
