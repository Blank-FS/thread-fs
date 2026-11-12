import type { ThreadFSCommentUser } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ScrollText } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { useRulesUrl } from "../../lib/rulesContext";
import defaultAvatarUrl from "../assets/default-avatar.png";
import AvatarFrame from "../card/AvatarFrame";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Skeleton } from "../ui/skeleton";
import RichEditor, { RichEditorValue } from "./RichEditor";

type CommentEditorProps = {
  isLoading?: boolean;
  currentUser?: ThreadFSCommentUser | null;
  placeholder?: string;
  submitLabel?: string;
  disabled?: boolean;
  initialMarkdown?: string | null;
  /** For a reply or an edit, which the viewer just asked for: starts focused, never shrinks, and has no avatar. */
  startOpen?: boolean;
  className?: string;
  onSubmit: (body: string) => Promise<void> | void;
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
  "text-muted-foreground hover:bg-primary/20 flex h-7 items-center gap-1 rounded-lg px-2 text-xs font-medium hover:cursor-pointer";

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
  startOpen = false,
  className,
  onSubmit,
  onAuthRequired,
  authorProfileUrl,
}: CommentEditorProps) {
  const [value, setValue] = useState<RichEditorValue>({
    markdown: initialMarkdown ?? "",
    text: initialMarkdown ?? "",
  });
  const [editorKey, setEditorKey] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isActive, setIsActive] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const rulesUrl = useRulesUrl();
  const isOpen = startOpen || isActive || value.text.trim().length > 0;

  // Only a click or focus elsewhere closes it. Losing focus isn't enough: its menus open outside it, in a portal
  useEffect(() => {
    if (!isActive) return;

    function closeIfOutside(event: Event) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (containerRef.current?.contains(target)) return;
      if (target.closest("[data-radix-popper-content-wrapper]")) return;
      setIsActive(false);
    }

    document.addEventListener("pointerdown", closeIfOutside);
    document.addEventListener("focusin", closeIfOutside);

    return () => {
      document.removeEventListener("pointerdown", closeIfOutside);
      document.removeEventListener("focusin", closeIfOutside);
    };
  }, [isActive]);

  const currentUsername = currentUser?.display_name ?? null;
  const currentUserAvatarUrl = currentUser?.avatar_url ?? null;

  const profileUrl = useMemo(() => {
    if (!currentUser || !authorProfileUrl) return null;
    return authorProfileUrl(currentUser);
  }, [currentUser, authorProfileUrl]);

  const canSubmit = value.text.trim().length > 0 && !disabled && !isSubmitting;

  async function handleSubmit() {
    if (!canSubmit) return;

    try {
      setIsSubmitting(true);
      await onSubmit(value.markdown);

      setValue(EMPTY_EDITOR_VALUE);
      setEditorKey((key) => key + 1);
      setIsActive(false);
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
      ref={containerRef}
      onFocusCapture={() => setIsActive(true)}
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
            actions={
              <>
                {/* The community's rules page, in a new tab so a half-written comment stays put; without one, a
                    short default */}
                {rulesUrl ? (
                  <a
                    href={rulesUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Rules"
                    title="Comment rules"
                    className={RULES_BUTTON_CLASS}
                  >
                    <ScrollText className="size-4" />
                    <span className="hidden @[12rem]:inline">Rules</span>
                  </a>
                ) : (
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      aria-label="Rules"
                      className={RULES_BUTTON_CLASS}
                    >
                      <ScrollText className="size-4" />
                      <span className="hidden @[12rem]:inline">Rules</span>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56 p-2.5">
                      <p className="text-sm">
                        Be respectful and keep the discussion on topic
                      </p>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
                <Button
                  type="button"
                  size="sm"
                  disabled={!canSubmit}
                  className="hover:cursor-pointer"
                  title={`${submitLabel} (${SUBMIT_KEY}+Enter)`}
                  aria-keyshortcuts="Control+Enter Meta+Enter"
                  onClick={handleSubmit}
                >
                  {isSubmitting ? "Posting..." : submitLabel}
                </Button>
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
