import { useGifConfig } from "@/lib/gifs";
import type { ThreadFSCommentUser, ThreadFSGif } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ScrollText, X } from "lucide-react";
import { useMemo, useState, type KeyboardEvent } from "react";
import { useRulesUrl } from "../../lib/rulesContext";
import defaultAvatarUrl from "../assets/default-avatar.png";
import AvatarFrame from "../card/AvatarFrame";
import { CommentGif } from "../card/CommentGif";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { Skeleton } from "../ui/skeleton";
import GifPicker from "./GifPicker";
import RichEditor, { RichEditorValue } from "./RichEditor";

type CommentEditorProps = {
  isLoading?: boolean;
  currentUser?: ThreadFSCommentUser | null;
  placeholder?: string;
  submitLabel?: string;
  disabled?: boolean;
  initialMarkdown?: string | null;
  /** The GIF an edited comment has. */
  initialGif?: ThreadFSGif | null;
  /** For a reply or an edit, which the viewer just asked for: starts focused, never shrinks, and has no avatar. */
  startOpen?: boolean;
  className?: string;
  /** The text, and the GIF under it (null for none). */
  onSubmit: (body: string, gif: ThreadFSGif | null) => Promise<void> | void;
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

const RULES_BUTTON_CLASS =
  "text-muted-foreground hover:bg-primary/20 flex h-7 min-w-7 items-center justify-center gap-1 rounded-lg px-1.5 text-xs font-medium hover:cursor-pointer @[17rem]:px-2";

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
  initialGif = null,
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
  const [gif, setGif] = useState<ThreadFSGif | null>(initialGif);
  const [isPickingGif, setIsPickingGif] = useState(false);
  const rulesUrl = useRulesUrl();
  const gifConfig = useGifConfig();
  const hasText = value.text.trim().length > 0;
  const isOpen = startOpen || isOpened;

  // Once opened it stays open until Cancel or posting: clicking elsewhere on the page (or into the GIF search, or a
  // menu) never closes it, as on Reddit. Cancel asks first when something would be lost.
  const [isConfirmingDiscard, setIsConfirmingDiscard] = useState(false);
  const hasChanges =
    value.markdown.trim() !== (initialMarkdown ?? "").trim() ||
    gif?.url !== initialGif?.url;

  function close() {
    setIsConfirmingDiscard(false);
    if (onCancel) {
      onCancel();
      return;
    }
    setValue(EMPTY_EDITOR_VALUE);
    setGif(null);
    setIsPickingGif(false);
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

  // A GIF alone is a comment
  const canSubmit = (hasText || gif !== null) && !disabled && !isSubmitting;

  async function handleSubmit() {
    if (!canSubmit) return;

    try {
      setIsSubmitting(true);
      await onSubmit(hasText ? value.markdown : "", gif);

      setValue(EMPTY_EDITOR_VALUE);
      setGif(null);
      setIsPickingGif(false);
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
                {gif && (
                  <div className="relative mt-1 w-fit">
                    <CommentGif gif={gif} className="my-0 max-h-32 w-auto" />
                    <button
                      type="button"
                      onClick={() => setGif(null)}
                      disabled={isSubmitting}
                      aria-label="Remove GIF"
                      title="Remove GIF"
                      className="bg-background/80 hover:bg-background absolute top-1 right-1 flex size-6 items-center justify-center rounded-full border hover:cursor-pointer"
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                )}
              </>
            }
            tools={
              // The search opens outside the box, over the page, as Reddit's does
              gifConfig && (
                <Popover open={isPickingGif} onOpenChange={setIsPickingGif}>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      disabled={disabled || isSubmitting}
                      aria-label={gif ? "Change GIF" : "Add a GIF"}
                      title={gif ? "Change GIF" : "Add a GIF"}
                      className={cn(
                        "text-muted-foreground hover:bg-primary/20 flex size-7 items-center justify-center rounded-lg hover:cursor-pointer disabled:opacity-50",
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
                        setGif(picked);
                        setIsPickingGif(false);
                      }}
                      onClose={() => setIsPickingGif(false)}
                    />
                  </PopoverContent>
                </Popover>
              )
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
