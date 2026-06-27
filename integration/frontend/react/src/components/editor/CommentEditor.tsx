import type { ThreadFSCommentUser } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";
import defaultAvatarUrl from "../assets/default-avatar.svg";
import { Button } from "../ui/button";
import { Skeleton } from "../ui/skeleton";
import RichEditor, { RichEditorValue } from "./RichEditor";

type CommentEditorProps = {
  isLoading?: boolean;
  currentUser?: ThreadFSCommentUser | null;
  placeholder?: string;
  submitLabel?: string;
  disabled?: boolean;
  initialMarkdown?: string | null;
  className?: string;
  onSubmit: (body: string) => Promise<void> | void;
  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;
};

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
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={cn("rounded-md border", className)}>
      {isLoading ? (
        <div className="flex items-center gap-3 border-b px-4 py-2">
          <Skeleton className="size-8 rounded-full" />
          <Skeleton className="h-4 w-full max-w-40 rounded" />
        </div>
      ) : (
        <div className="flex items-center gap-3 border-b px-4 py-2">
          {profileUrl ? (
            <a href={profileUrl} className="shrink-0">
              <img
                src={currentUserAvatarUrl ?? defaultAvatarUrl}
                alt={
                  currentUsername
                    ? `${currentUsername}'s avatar`
                    : "Default avatar"
                }
                className="border-muted bg-background size-8 rounded-full border object-cover"
              />
            </a>
          ) : (
            <img
              src={currentUserAvatarUrl ?? defaultAvatarUrl}
              alt={
                currentUsername
                  ? `${currentUsername}'s avatar`
                  : "Default avatar"
              }
              className="border-muted bg-background size-8 rounded-full border object-cover"
            />
          )}

          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {currentUsername ? (
                <>
                  Comment as{" "}
                  {profileUrl ? (
                    <a
                      href={profileUrl}
                      className="text-cyan-500 hover:underline dark:text-cyan-200"
                    >
                      {currentUsername}
                    </a>
                  ) : (
                    <span className="text-cyan-500 dark:text-cyan-200">
                      {currentUsername}
                    </span>
                  )}
                </>
              ) : (
                <>
                  You must{" "}
                  {onAuthRequired ? (
                    <button
                      type="button"
                      onClick={onAuthRequired}
                      className="text-cyan-500 hover:cursor-pointer hover:underline dark:text-cyan-200"
                    >
                      log in
                    </button>
                  ) : (
                    "log in"
                  )}{" "}
                  to comment
                </>
              )}
            </p>
          </div>
        </div>
      )}

      <div className="px-4 py-2">
        <RichEditor
          key={editorKey}
          initialMarkdown={initialMarkdown}
          disabled={disabled || isSubmitting}
          placeholder={placeholder}
          onChange={setValue}
        />
      </div>

      <div className="flex items-center justify-between gap-4 border-t px-4 py-2">
        <p className="text-muted-foreground text-xs">
          Be respectful and keep the discussion on topic
        </p>

        <Button type="button" disabled={!canSubmit} onClick={handleSubmit}>
          {isSubmitting ? "Posting..." : submitLabel}
        </Button>
      </div>
    </div>
  );
}

export default CommentEditor;
