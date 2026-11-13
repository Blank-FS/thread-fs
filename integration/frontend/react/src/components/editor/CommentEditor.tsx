import { useGifConfig } from "@/lib/gifs";
import { useImageHosts } from "@/lib/imageHosts";
import type { CommentMedia, ThreadFSCommentUser } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ImagePlus, ScrollText, X } from "lucide-react";
import { useMemo, useState, type KeyboardEvent } from "react";
import { useRulesUrl } from "../../lib/rulesContext";
import defaultAvatarUrl from "../assets/default-avatar.png";
import AvatarFrame from "../card/AvatarFrame";
import { CommentGif } from "../card/CommentGif";
import { CommentImage } from "../card/CommentMedia";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { Skeleton } from "../ui/skeleton";
import GifPicker from "./GifPicker";
import ImageLinkForm from "./ImageLinkForm";
import RichEditor, { RichEditorValue } from "./RichEditor";

type CommentEditorProps = {
  isLoading?: boolean;
  currentUser?: ThreadFSCommentUser | null;
  placeholder?: string;
  submitLabel?: string;
  disabled?: boolean;
  initialMarkdown?: string | null;
  /** The GIF or image an edited comment has. */
  initialMedia?: CommentMedia;
  /** For a reply or an edit, which the viewer just asked for: starts focused, never shrinks, and has no avatar. */
  startOpen?: boolean;
  className?: string;
  /** The text, and the GIF or image under it. */
  onSubmit: (body: string, media: CommentMedia) => Promise<void> | void;
  /** Cancel closes a reply or edit box; without it, Cancel just closes this one back down. */
  onCancel?: () => void;
  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;
};

// ⌘ on Apple devices, Ctrl elsewhere, for the shortcut's hint
const SUBMIT_KEY =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad/.test(navigator.userAgent)
    ? "⌘"
    : "Ctrl";

// Left out of the narrowest boxes (deep replies on phones), which need the room; the top comment box always has it
const RULES_BUTTON_CLASS =
  "text-muted-foreground hover:bg-primary/20 hidden @[15rem]:flex h-7 min-w-7 items-center justify-center gap-1 rounded-lg px-1.5 text-xs font-medium hover:cursor-pointer @[17rem]:px-2";

const NO_MEDIA: CommentMedia = { gif: null, image: null };

// The image and GIF buttons: dimmed while the comment already has one or the other
const MEDIA_BUTTON_CLASS =
  "text-muted-foreground hover:bg-primary/20 flex size-7 items-center justify-center rounded-lg hover:cursor-pointer disabled:cursor-default disabled:opacity-40 disabled:hover:bg-transparent";

const EMPTY_EDITOR_VALUE: RichEditorValue = {
  markdown: "",
  text: "",
};

function CommentEditor({
  isLoading = false,
  currentUser = null,
  placeholder = "Join the discussion...",
  submitLabel = "Post",
  disabled = false,
  initialMarkdown = null,
  initialMedia = NO_MEDIA,
  startOpen = false,
  className,
  onSubmit,
  onCancel,
  onAuthRequired,
  authorProfileUrl,
}: CommentEditorProps) {
  const [value, setValue] = useState<RichEditorValue>({
    markdown: initialMarkdown ?? "",
    text: initialMarkdown ?? "",
  });
  const [editorKey, setEditorKey] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Opened by focusing it; closed only by Cancel or posting
  const [isOpened, setIsOpened] = useState(false);
  // One GIF or one image, as on Reddit: once either is attached, both buttons wait until it's removed
  const [media, setMedia] = useState<CommentMedia>(initialMedia);
  const hasMedia = media.gif !== null || media.image !== null;
  const [isPickingGif, setIsPickingGif] = useState(false);
  const [isAddingImage, setIsAddingImage] = useState(false);
  const rulesUrl = useRulesUrl();
  const gifConfig = useGifConfig();
  const imageHosts = useImageHosts();
  const hasText = value.text.trim().length > 0;
  const isOpen = startOpen || isOpened;

  // Once opened it stays open until Cancel or posting: clicking elsewhere on the page (or into the GIF search, or a
  // menu) never closes it, as on Reddit. Cancel asks first when something would be lost.
  const [isConfirmingDiscard, setIsConfirmingDiscard] = useState(false);
  const hasChanges =
    value.markdown.trim() !== (initialMarkdown ?? "").trim() ||
    media.gif?.url !== initialMedia.gif?.url ||
    media.image?.url !== initialMedia.image?.url;

  function close() {
    setIsConfirmingDiscard(false);
    if (onCancel) {
      onCancel();
      return;
    }
    setValue(EMPTY_EDITOR_VALUE);
    setMedia(NO_MEDIA);
    setIsPickingGif(false);
    setIsAddingImage(false);
    setEditorKey((key) => key + 1);
    setIsOpened(false);
  }

  function handleCancel() {
    if (hasChanges) setIsConfirmingDiscard(true);
    else close();
  }

  const currentUsername = currentUser?.display_name ?? null;
  const currentUserAvatarUrl = currentUser?.avatar_url ?? null;

  const profileUrl = useMemo(() => {
    if (!currentUser || !authorProfileUrl) return null;
    return authorProfileUrl(currentUser);
  }, [currentUser, authorProfileUrl]);

  // A GIF or an image alone is a comment
  const canSubmit = (hasText || hasMedia) && !disabled && !isSubmitting;

  async function handleSubmit() {
    if (!canSubmit) return;

    try {
      setIsSubmitting(true);
      await onSubmit(hasText ? value.markdown : "", media);

      setValue(EMPTY_EDITOR_VALUE);
      setMedia(NO_MEDIA);
      setIsPickingGif(false);
      setIsAddingImage(false);
      setEditorKey((key) => key + 1);
      setIsOpened(false);
    } finally {
      setIsSubmitting(false);
    }
  }

  // Ctrl+Enter (⌘+Enter on a Mac) posts, as on GitHub and Reddit; Enter alone is a new line, since comments are written
  // in paragraphs. Caught before the editor sees the key, so it works in both its modes.
  function handleSubmitShortcut(event: KeyboardEvent) {
    if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
    if (event.nativeEvent.isComposing) return; // Confirming an IME composition
    event.preventDefault();
    event.stopPropagation();
    void handleSubmit();
  }

  const avatar = (
    <img
      src={currentUserAvatarUrl ?? defaultAvatarUrl}
      onError={(e) => {
        e.currentTarget.src = defaultAvatarUrl;
        e.currentTarget.onerror = null;
      }}
      alt={currentUsername ? `${currentUsername}'s avatar` : "Default avatar"}
      className="border-muted bg-background size-8 rounded-full border object-cover"
    />
  );

  return (
    <div
      onFocusCapture={() => setIsOpened(true)}
      className={cn("flex gap-3", className)}
    >
      {/* The reply or comment being edited already sits beside an avatar, and a reply deep in a thread needs the width.
          Here it lines up with the avatars of the comments below, and level with the input. */}
      {!startOpen && (
        <div className="shrink-0 pt-[5px]">
          {isLoading ? (
            <Skeleton className="size-8 rounded-full" />
          ) : (
            <div className="relative size-8">
              {profileUrl ? <a href={profileUrl}>{avatar}</a> : avatar}
              <AvatarFrame url={currentUser?.avatar_frame_url} />
            </div>
          )}
        </div>
      )}

      <div
        onKeyDownCapture={handleSubmitShortcut}
        className="min-w-0 flex-1 rounded-md border px-2 py-1"
      >
        {isLoading ? (
          <Skeleton className="h-8 w-full rounded" />
        ) : currentUser ? (
          <RichEditor
            key={editorKey}
            autoFocus={startOpen}
            initialMarkdown={initialMarkdown}
            disabled={disabled || isSubmitting}
            placeholder={placeholder}
            onChange={setValue}
            showControls={isOpen}
            // "Discard?" and its buttons take the whole row, so they fit the narrowest reply box
            actionsOnly={isConfirmingDiscard}
            attachments={
              <>
                {hasMedia && (
                  <div className="relative mt-1 w-fit">
                    {media.gif ? (
                      <CommentGif
                        gif={media.gif}
                        className="my-0 max-h-32 w-auto"
                      />
                    ) : (
                      media.image && (
                        <CommentImage
                          image={media.image}
                          className="my-0 max-h-32 w-auto"
                        />
                      )
                    )}
                    <button
                      type="button"
                      onClick={() => setMedia(NO_MEDIA)}
                      disabled={isSubmitting}
                      aria-label={media.gif ? "Remove GIF" : "Remove image"}
                      title={media.gif ? "Remove GIF" : "Remove image"}
                      className="bg-background/80 hover:bg-background absolute top-1 right-1 flex size-6 items-center justify-center rounded-full border hover:cursor-pointer"
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                )}
              </>
            }
            tools={
              <>
                {/* A link to an image on one of the community's image hosts: there are no uploads. Only offered when
                    there are hosts */}
                {imageHosts.length > 0 && (
                  <Popover open={isAddingImage} onOpenChange={setIsAddingImage}>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        disabled={disabled || isSubmitting || hasMedia}
                        aria-label="Add an image"
                        title={
                          hasMedia
                            ? `Remove the ${media.gif ? "GIF" : "image"} to add an image`
                            : "Add an image"
                        }
                        className={cn(
                          MEDIA_BUTTON_CLASS,
                          isAddingImage && "bg-primary/20 text-foreground",
                        )}
                      >
                        <ImagePlus className="size-4" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[min(22rem,calc(100vw-1rem))] p-0">
                      <ImageLinkForm
                        hosts={imageHosts}
                        onAdd={(image) => {
                          setMedia({ gif: null, image });
                          setIsAddingImage(false);
                        }}
                        onCancel={() => setIsAddingImage(false)}
                      />
                    </PopoverContent>
                  </Popover>
                )}

                {/* The search opens outside the box, over the page, as Reddit's does */}
                {gifConfig && (
                  <Popover open={isPickingGif} onOpenChange={setIsPickingGif}>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        disabled={disabled || isSubmitting || hasMedia}
                        aria-label="Add a GIF"
                        title={
                          hasMedia
                            ? `Remove the ${media.gif ? "GIF" : "image"} to add a GIF`
                            : "Add a GIF"
                        }
                        className={cn(
                          MEDIA_BUTTON_CLASS,
                          isPickingGif && "bg-primary/20 text-foreground",
                        )}
                      >
                        <span className="rounded-[3px] border border-current px-0.5 text-[9px] leading-[11px] font-bold">
                          GIF
                        </span>
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[min(22rem,calc(100vw-1rem))] p-0">
                      <GifPicker
                        config={gifConfig}
                        onPick={(picked) => {
                          setMedia({ gif: picked, image: null });
                          setIsPickingGif(false);
                        }}
                        onClose={() => setIsPickingGif(false)}
                      />
                    </PopoverContent>
                  </Popover>
                )}
              </>
            }
            actions={
              <>
                {/* The community's rules page, in a new tab so a half-written comment stays put; without one, a
                    short default */}
                {isConfirmingDiscard ? null : rulesUrl ? (
                  <a
                    href={rulesUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Rules"
                    title="Comment rules"
                    className={RULES_BUTTON_CLASS}
                  >
                    <ScrollText className="size-4" />
                    <span className="hidden @[17rem]:inline">Rules</span>
                  </a>
                ) : (
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      aria-label="Rules"
                      className={RULES_BUTTON_CLASS}
                    >
                      <ScrollText className="size-4" />
                      <span className="hidden @[17rem]:inline">Rules</span>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56 p-2.5">
                      <p className="text-sm">
                        Be respectful and keep the discussion on topic
                      </p>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
                {isConfirmingDiscard ? (
                  <>
                    <span className="text-muted-foreground px-1 text-xs">
                      Discard?
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="px-2 hover:cursor-pointer"
                      onClick={() => setIsConfirmingDiscard(false)}
                    >
                      Keep
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      className="px-2 hover:cursor-pointer"
                      onClick={close}
                    >
                      Discard
                    </Button>
                  </>
                ) : (
                  <>
                    {/* Outlined, so it stands apart from the icons beside it */}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={isSubmitting}
                      className="px-2 hover:cursor-pointer"
                      onClick={handleCancel}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      disabled={!canSubmit}
                      className="px-2 hover:cursor-pointer"
                      title={`${submitLabel} (${SUBMIT_KEY}+Enter)`}
                      aria-keyshortcuts="Control+Enter Meta+Enter"
                      onClick={handleSubmit}
                    >
                      {isSubmitting ? "Posting..." : submitLabel}
                    </Button>
                  </>
                )}
              </>
            }
          />
        ) : onAuthRequired ? (
          <button
            type="button"
            onClick={onAuthRequired}
            className="text-muted-foreground flex min-h-8 w-full items-center p-1 text-left text-base hover:cursor-text"
          >
            {placeholder}
          </button>
        ) : (
          <p className="text-muted-foreground flex min-h-8 items-center p-1 text-base">
            Log in to comment
          </p>
        )}
      </div>
    </div>
  );
}

export default CommentEditor;
