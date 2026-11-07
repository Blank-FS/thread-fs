import { useEffect, useState } from "react";
import { searchUsers } from "../../lib/moderationApi";
import type { ModerationUser, ThreadFSCommentUser } from "../../lib/types";
import { Input } from "../ui/input";
import { useModeration, UserAvatar, userName } from "./shared";

/** Finds a user by name or id as you type. */
export function UserPicker({
  label,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: ThreadFSCommentUser | null;
  onChange: (user: ThreadFSCommentUser | null) => void;
}) {
  const { request } = useModeration();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ModerationUser[]>([]);

  useEffect(() => {
    const search = query.trim();

    if (!search) {
      setMatches([]);
      return;
    }

    let isCurrent = true;
    const timer = window.setTimeout(() => {
      request((ctx) => searchUsers(ctx, { q: search, limit: 6, offset: 0 }))
        .then((page) => {
          if (isCurrent) setMatches(page.items);
        })
        .catch(() => {
          if (isCurrent) setMatches([]);
        });
    }, 250);

    return () => {
      isCurrent = false;
      window.clearTimeout(timer);
    };
  }, [query, request]);

  if (value) {
    return (
      <div className="border-input flex h-8 items-center gap-2 rounded-lg border pr-2.5 pl-1.5 text-sm">
        <UserAvatar user={value} size="sm" frame={false} />
        <span className="min-w-0 flex-1 truncate">{userName(value)}</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-muted-foreground shrink-0 hover:cursor-pointer hover:underline"
        >
          Clear
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label={label}
        placeholder={placeholder}
        className="md:text-sm"
      />
      {matches.length > 0 && (
        <ul className="bg-popover ring-foreground/10 absolute z-20 mt-1 w-full overflow-hidden rounded-lg p-1 shadow-md ring-1">
          {matches.map((user) => (
            <li key={user.id}>
              <button
                type="button"
                onClick={() => {
                  onChange(user);
                  setQuery("");
                }}
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-sm hover:cursor-pointer"
              >
                <UserAvatar user={user} size="sm" frame={false} />
                <span className="min-w-0 flex-1 truncate">
                  {userName(user)}
                </span>
                <span className="text-muted-foreground shrink-0 text-xs">
                  {user.comment_count}{" "}
                  {user.comment_count === 1 ? "comment" : "comments"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
