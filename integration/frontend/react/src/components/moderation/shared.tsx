import { Inbox } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import type {
  CommunityBan,
  ModerationComment,
  PageResponse,
  ThreadFSCommentUser,
  ThreadFSReason,
  ThreadFSRequestContext,
  ThreadFSThread,
} from "../../lib/types";
import { cn } from "../../lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "../ui/avatar";
import { Button } from "../ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { Skeleton } from "../ui/skeleton";

export type ModerationRequest = <T>(
  action: (ctx: ThreadFSRequestContext) => Promise<T>,
) => Promise<T>;

type ModerationContextValue = {
  request: ModerationRequest;
  reasons: ThreadFSReason[];
  pageSize: number;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;
  threadUrl?: (comment: Pick<ModerationComment, "thread">) => string | null;
  /** Goes up whenever something changed that open lists should show. */
  version: number;
  refresh: () => void;
  onOpenReports: (count: number) => void;
  /** Re-counts open reports, after anything that may have closed some. */
  syncOpenReports: () => void;
  setReasons: (reasons: ThreadFSReason[]) => void;
  openUser: (user: ThreadFSCommentUser) => void;
  showUserComments: (user: ThreadFSCommentUser) => void;
  showUserLog: (user: ThreadFSCommentUser) => void;
  showThreadComments: (thread: ThreadFSThread) => void;
};

const ModerationContext = createContext<ModerationContextValue | null>(null);

export const ModerationProvider = ModerationContext.Provider;

export function useModeration() {
  const value = useContext(ModerationContext);
  if (!value) throw new Error("Used outside ThreadFSModeration");
  return value;
}

/** The widget's main action, in the community's accent colour. */
export const brandButtonClass =
  "bg-tfs-brand-strong dark:bg-tfs-brand text-white hover:opacity-90 hover:cursor-pointer dark:text-black";

export const BAN_LENGTHS = [
  { label: "1 day", value: "1" },
  { label: "7 days", value: "7" },
  { label: "30 days", value: "30" },
  { label: "Permanent", value: "" },
];

/** The expiry for a value from BAN_LENGTHS, null being permanent. */
export function banExpiry(days: string) {
  return days
    ? new Date(Date.now() + Number(days) * 86_400_000).toISOString()
    : null;
}

export function userName(user?: ThreadFSCommentUser | null) {
  return user?.display_name?.trim() || "Anonymous";
}

export function isBanActive(ban: CommunityBan) {
  return (
    !ban.lifted_at &&
    (!ban.expires_at || new Date(ban.expires_at).getTime() > Date.now())
  );
}

export function banTerm(ban: CommunityBan) {
  const date = (value: string) => new Date(value).toLocaleString();

  if (ban.lifted_at) return `Lifted ${date(ban.lifted_at)}`;
  if (!ban.expires_at) return "Permanent";
  return isBanActive(ban)
    ? `Until ${date(ban.expires_at)}`
    : `Ended ${date(ban.expires_at)}`;
}

export function errorMessage(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback;
}

// A Select item can't have an empty value, so "no choice" travels as this
const NO_VALUE = "__none";

/** A labelled dropdown. An option with an empty value means "no choice". */
export function ChoiceSelect({
  label,
  value,
  options,
  onChange,
  className,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <Select
      value={value || NO_VALUE}
      onValueChange={(next) => onChange(next === NO_VALUE ? "" : next)}
    >
      <SelectTrigger
        aria-label={label}
        className={cn("w-full hover:cursor-pointer", className)}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem
            key={option.value || NO_VALUE}
            value={option.value || NO_VALUE}
          >
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function ReasonSelect({
  value,
  onChange,
  extraOptions = [],
  className,
}: {
  value: string;
  onChange: (key: string) => void;
  extraOptions?: { value: string; label: string }[];
  className?: string;
}) {
  const { reasons } = useModeration();

  return (
    <ChoiceSelect
      label="Reason shown to the author"
      value={value}
      onChange={onChange}
      className={className}
      options={[
        ...extraOptions,
        { value: "", label: "No reason given" },
        ...reasons.map(({ key, label }) => ({ value: key, label })),
      ]}
    />
  );
}

export function BanLengthSelect({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (days: string) => void;
  className?: string;
}) {
  return (
    <ChoiceSelect
      label="Ban length"
      value={value}
      onChange={onChange}
      options={BAN_LENGTHS}
      className={className}
    />
  );
}

export function UserAvatar({
  user,
  size,
}: {
  user?: ThreadFSCommentUser | null;
  size?: "sm" | "default" | "lg";
}) {
  return (
    <Avatar size={size}>
      {user?.avatar_url && (
        <AvatarImage
          src={user.avatar_url}
          alt=""
          referrerPolicy="no-referrer"
        />
      )}
      <AvatarFallback>
        {userName(user).slice(0, 2).toUpperCase()}
      </AvatarFallback>
    </Avatar>
  );
}

/** A name that opens that user's panel. */
export function UserLink({ user }: { user?: ThreadFSCommentUser | null }) {
  const { openUser } = useModeration();

  if (!user) return <span className="font-semibold">Anonymous</span>;

  return (
    <button
      type="button"
      onClick={() => openUser(user)}
      className="text-tfs-brand-strong dark:text-tfs-brand font-semibold hover:cursor-pointer hover:underline"
    >
      {userName(user)}
    </button>
  );
}

export type PagedList<T> = {
  items: T[];
  setItems: Dispatch<SetStateAction<T[]>>;
  total: number | null;
  isLoading: boolean;
  isLoadingMore: boolean;
  isBusy: boolean;
  hasMore: boolean;
  error: string | null;
  loadMore: () => void;
  reload: () => void;
  /** Runs an action, showing any error on the list. Resolves to whether it worked. */
  run: (work: () => Promise<unknown>) => Promise<boolean>;
};

export function usePagedList<T>(
  load: (limit: number, offset: number) => Promise<PageResponse<T>>,
): PagedList<T> {
  const { pageSize, version } = useModeration();
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Only the newest request may fill the list, however the answers arrive
  const latest = useRef(0);

  const reload = useCallback(async () => {
    const id = ++latest.current;

    try {
      setError(null);
      const page = await load(pageSize, 0);
      if (id !== latest.current) return;
      setItems(page.items);
      setTotal(page.total);
      setNextOffset(page.next_offset);
    } catch (err: unknown) {
      if (id === latest.current) setError(errorMessage(err, "Failed to load"));
    } finally {
      if (id === latest.current) setIsLoading(false);
    }
  }, [load, pageSize]);

  useEffect(() => {
    setIsLoading(true);
    void reload();
  }, [reload, version]);

  async function loadMore() {
    if (nextOffset == null || isLoadingMore) return;
    const id = ++latest.current;

    try {
      setIsLoadingMore(true);
      setError(null);
      const page = await load(pageSize, nextOffset);
      if (id !== latest.current) return;
      setItems((current) => [...current, ...page.items]);
      setTotal(page.total);
      setNextOffset(page.next_offset);
    } catch (err: unknown) {
      if (id === latest.current) setError(errorMessage(err, "Failed to load"));
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function run(work: () => Promise<unknown>) {
    try {
      setIsBusy(true);
      setError(null);
      await work();
      return true;
    } catch (err: unknown) {
      setError(errorMessage(err, "Action failed"));
      return false;
    } finally {
      setIsBusy(false);
    }
  }

  return {
    items,
    setItems,
    total,
    isLoading,
    isLoadingMore,
    isBusy,
    hasMore: nextOffset != null,
    error,
    loadMore: () => void loadMore(),
    reload: () => void reload(),
    run,
  };
}

export function ListBody<T>({
  list,
  empty,
  icon,
  children,
}: {
  list: PagedList<T>;
  empty: string;
  icon?: typeof Inbox;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      {list.error && <ErrorNote>{list.error}</ErrorNote>}

      {list.items.length > 0 ? (
        // Old results stay, dimmed, until new ones arrive, so typing in a filter doesn't flash the page
        <div
          className={cn(
            "space-y-2 transition-opacity",
            list.isLoading && "opacity-60",
          )}
        >
          {children}
        </div>
      ) : list.isLoading ? (
        <ListSkeleton />
      ) : (
        !list.error && <EmptyNote icon={icon}>{empty}</EmptyNote>
      )}

      {list.hasMore && (
        <div className="flex justify-center pt-2">
          <Button
            type="button"
            variant="secondary"
            disabled={list.isLoadingMore}
            onClick={list.loadMore}
            className="hover:cursor-pointer hover:underline"
          >
            {list.isLoadingMore ? "Loading..." : "Load more"}
          </Button>
        </div>
      )}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {children}
    </div>
  );
}

export function EmptyNote({
  children,
  icon: Icon = Inbox,
}: {
  children: ReactNode;
  icon?: typeof Inbox;
}) {
  return (
    <div className="text-muted-foreground flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-12 text-center text-sm">
      <Icon className="size-6" />
      <p>{children}</p>
    </div>
  );
}

export function ListSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map((item) => (
        <Skeleton key={item} className="h-28 w-full rounded-xl" />
      ))}
    </div>
  );
}
