import {
  Ban,
  Check,
  Eye,
  EyeOff,
  FlagOff,
  ImageOff,
  Lock,
  LockOpen,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { linkToComment } from "../../lib/commentLinks";
import {
  addNote,
  banUser,
  batchComments,
  deleteNote,
  getUser,
  liftBan,
  listActions,
  listBans,
  searchComments,
  searchUsers,
  undoBatch,
  type BanSort,
  type BanStatus,
  type UserSort,
} from "../../lib/moderationApi";
import type {
  CommunityBan,
  ModerationAction,
  ModerationComment,
  ModerationUser,
  ModerationUserDetail,
  ThreadFSCommentUser,
} from "../../lib/types";
import CommentTimestamp from "../card/CommentTimestamp";
import { MarkdownContent } from "../common/MarkdownContent";
import { GifLabel } from "../card/CommentGif";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { Separator } from "../ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "../ui/sheet";
import { ListStatus } from "./ListStatus";
import {
  banBlockedReason,
  banExpiry,
  BanLengthSelect,
  banTerm,
  canLiftBan,
  ChoiceSelect,
  errorMessage,
  ErrorNote,
  isBanActive,
  ListBody,
  ListSkeleton,
  ReasonSelect,
  StaffBadge,
  useModeration,
  usePagedList,
  UserAvatar,
  UserLink,
  userName,
  type PagedList,
} from "./shared";
import { UserPicker } from "./UserPicker";

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? "" : "s"}`;

function SearchInput({
  value,
  onChange,
  label,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder: string;
}) {
  return (
    <div className="relative">
      <Search className="text-muted-foreground absolute top-2 left-2.5 size-4" />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label}
        placeholder={placeholder}
        className="pl-8 md:text-sm"
      />
    </div>
  );
}

/** Text that only takes effect once typing pauses. */
function useSettled(text: string) {
  const [settled, setSettled] = useState(text);

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(text.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [text]);

  return settled;
}

export function UsersPanel() {
  const { request, openUser } = useModeration();
  const [query, setQuery] = useState("");
  const search = useSettled(query);
  const [only, setOnly] = useState("");
  const [sort, setSort] = useState<UserSort>("name");

  const load = useCallback(
    (limit: number, offset: number) =>
      request((ctx) =>
        searchUsers(ctx, {
          q: search,
          only: only || undefined,
          sort,
          limit,
          offset,
        }),
      ),
    [request, search, only, sort],
  );
  const list = usePagedList<ModerationUser>(load);

  return (
    <div className="space-y-3">
      <div className="grid gap-2 @xl:grid-cols-[1fr_11rem_11rem]">
        <SearchInput
          value={query}
          onChange={setQuery}
          label="Search users"
          placeholder="Search by name or id"
        />
        <ChoiceSelect
          label="Filter users"
          value={only}
          onChange={setOnly}
          options={[
            { value: "", label: "All users" },
            { value: "banned", label: "Banned" },
            { value: "removed", label: "Comments removed" },
            { value: "reported", label: "Reported" },
          ]}
        />
        <ChoiceSelect
          label="Sort users"
          value={sort}
          onChange={(value) => setSort(value as UserSort)}
          options={[
            { value: "name", label: "Name" },
            { value: "newest", label: "Newest" },
            { value: "most_comments", label: "Most comments" },
            { value: "most_removed", label: "Most removed" },
            { value: "most_reported", label: "Most reported" },
          ]}
        />
      </div>

      <div className="flex items-center">
        <ListStatus
          list={list as PagedList<unknown>}
          label={list.total === 1 ? "user" : "users"}
        />
      </div>

      <ListBody list={list} empty="No users found" icon={Users}>
        {list.items.map((user) => (
          <button
            key={user.id}
            type="button"
            onClick={() => openUser(user)}
            className="w-full text-left hover:cursor-pointer"
          >
            <Card className="hover:bg-muted/50 flex-row items-center gap-3 p-3 transition-colors">
              <UserAvatar user={user} />
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2">
                  <span className="truncate font-semibold">
                    {userName(user)}
                  </span>
                  <StaffBadge user={user} />
                  {user.is_banned && (
                    <Badge variant="destructive">Banned</Badge>
                  )}
                </p>
                <p className="text-muted-foreground truncate text-xs">
                  {plural(user.comment_count, "comment")} · {user.removed_count}{" "}
                  removed · {plural(user.report_count, "report")}
                </p>
              </div>
            </Card>
          </button>
        ))}
      </ListBody>
    </div>
  );
}

export function BansPanel() {
  const { request, refresh } = useModeration();
  const [query, setQuery] = useState("");
  const search = useSettled(query);
  const [status, setStatus] = useState<BanStatus>("active");
  const [length, setLength] = useState("");
  const [bannedBy, setBannedBy] = useState<ThreadFSCommentUser | null>(null);
  const [sort, setSort] = useState<BanSort>("newest");

  const load = useCallback(
    (limit: number, offset: number) =>
      request((ctx) =>
        listBans(ctx, {
          status,
          length: length || undefined,
          q: search,
          bannedBy: bannedBy?.id,
          sort,
          limit,
          offset,
        }),
      ),
    [request, status, length, search, bannedBy, sort],
  );
  const list = usePagedList<CommunityBan>(load);

  async function lift(banId: number) {
    if (await list.run(() => request((ctx) => liftBan(ctx, banId)))) refresh();
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-2 @xl:grid-cols-2">
        <SearchInput
          value={query}
          onChange={setQuery}
          label="Search bans"
          placeholder="Search by user"
        />
        <UserPicker
          label="Banned by"
          placeholder="Banned by"
          value={bannedBy}
          onChange={setBannedBy}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <ChoiceSelect
          label="Ban status"
          value={status}
          onChange={(value) => setStatus(value as BanStatus)}
          className="w-32"
          options={[
            { value: "active", label: "Active" },
            { value: "expired", label: "Expired" },
            { value: "lifted", label: "Lifted" },
            { value: "all", label: "All bans" },
          ]}
        />
        <ChoiceSelect
          label="Ban length filter"
          value={length}
          onChange={setLength}
          className="w-36"
          options={[
            { value: "", label: "Any length" },
            { value: "temporary", label: "Temporary" },
            { value: "permanent", label: "Permanent" },
          ]}
        />
        <ChoiceSelect
          label="Sort bans"
          value={sort}
          onChange={(value) => setSort(value as BanSort)}
          className="w-36"
          options={[
            { value: "newest", label: "Newest" },
            { value: "oldest", label: "Oldest" },
            { value: "ending_soon", label: "Ending soon" },
          ]}
        />
        <ListStatus
          list={list as PagedList<unknown>}
          label={list.total === 1 ? "ban" : "bans"}
        />
      </div>

      <ListBody list={list} empty="No bans" icon={Ban}>
        {list.items.map((ban) => (
          <Card key={ban.id} className="flex-row items-center gap-3 p-3">
            <UserAvatar user={ban.community_user} />
            <div className="min-w-0 flex-1">
              <UserLink user={ban.community_user} />
              <p className="text-muted-foreground text-xs">
                {banTerm(ban)}
                {ban.banned_by && ` · Banned by ${userName(ban.banned_by)}`}
                {ban.lifted_by && ` · Lifted by ${userName(ban.lifted_by)}`}
              </p>
              {ban.reason && <p className="mt-1">{ban.reason}</p>}
            </div>
            {isBanActive(ban) && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={list.isBusy}
                className="hover:cursor-pointer"
                onClick={() => void lift(ban.id)}
              >
                Lift ban
              </Button>
            )}
          </Card>
        ))}
      </ListBody>
    </div>
  );
}

/** What a log entry says happened. Targets are links, like every other name here. */
function ActionText({ action, target, batch }: ModerationAction) {
  const who = <UserLink user={target} />;
  const count = batch?.comment_count ?? 0;
  const comments = `${count} ${count === 1 ? "comment" : "comments"}`;

  switch (action) {
    case "hide_batch":
      return <>removed {comments}</>;
    case "restore_batch":
      return <>restored {comments}</>;
    case "update_limits":
      return <>changed the moderator limits</>;
    case "update_rules":
      return <>changed the comment rules link</>;
    case "update_gifs":
      return <>changed the GIF settings</>;
    case "undo_batch":
      return <>undid a batch of {comments}</>;
    case "hide_comment":
      return <>removed {who}'s comment</>;
    case "restore_comment":
      return <>restored {who}'s comment</>;
    case "ban_user":
      return <>banned {who}</>;
    case "unban_user":
      return <>lifted {who}'s ban</>;
    case "lock_thread":
      return <>locked a thread</>;
    case "unlock_thread":
      return <>unlocked a thread</>;
    case "dismiss_reports":
      return <>dismissed reports on {who}'s comment</>;
    case "resolve_reports":
      return <>resolved reports on {who}'s comment</>;
    case "reopen_reports":
      return <>reopened reports on {who}'s comment</>;
    case "clear_avatar":
      return <>cleared {who}'s avatar</>;
    case "clear_avatar_frame":
      return <>cleared {who}'s avatar frame</>;
    default:
      return <>{action}</>;
  }
}

/** What a log entry was about: the comment if it has one, and where it is. */
function ActionSubject({ entry }: { entry: ModerationAction }) {
  const { threadUrl } = useModeration();
  const { comment, thread } = entry;

  if (!comment && !thread) return null;

  const threadHref = threadUrl
    ? threadUrl({ thread })
    : (thread?.source_url ?? null);
  // Straight to the comment when the entry has one, else the thread
  const href = comment ? linkToComment(threadHref, comment.id) : threadHref;
  const title = thread?.title || thread?.unique_id;

  return (
    <div className="bg-muted/50 mt-1.5 rounded-md px-2.5 py-1.5 text-xs">
      {comment &&
        (comment.status === "deleted" ? (
          <p className="text-muted-foreground italic">
            Since deleted by its author
          </p>
        ) : (
          <div className="line-clamp-2 [&_*]:mb-0 [&_*]:text-xs [&_*]:leading-5">
            {comment.gif && <GifLabel />}
            <MarkdownContent markdown={comment.content} />
          </div>
        ))}
      {title &&
        (href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground block truncate hover:underline"
          >
            {title}
          </a>
        ) : (
          <p className="text-muted-foreground truncate">{title}</p>
        ))}
    </div>
  );
}

const ACTION_ICONS: Record<string, typeof Ban> = {
  hide_comment: EyeOff,
  restore_comment: Eye,
  hide_batch: EyeOff,
  restore_batch: Eye,
  undo_batch: RotateCcw,
  update_limits: SlidersHorizontal,
  ban_user: Ban,
  unban_user: ShieldCheck,
  lock_thread: Lock,
  unlock_thread: LockOpen,
  dismiss_reports: FlagOff,
  resolve_reports: Check,
  reopen_reports: RotateCcw,
  clear_avatar: ImageOff,
  clear_avatar_frame: ImageOff,
};

const LOG_ACTIONS = [
  { value: "", label: "All actions" },
  { value: "hide_comment", label: "Removed comments" },
  { value: "restore_comment", label: "Restored comments" },
  { value: "ban_user", label: "Bans" },
  { value: "unban_user", label: "Lifted bans" },
  { value: "lock_thread", label: "Locked threads" },
  { value: "unlock_thread", label: "Unlocked threads" },
  { value: "dismiss_reports", label: "Dismissed reports" },
  { value: "reopen_reports", label: "Reopened reports" },
];

const toIso = (local: string) =>
  local ? new Date(local).toISOString() : undefined;

export function LogPanel({
  target,
  onTarget,
}: {
  target: ThreadFSCommentUser | null;
  onTarget: (user: ThreadFSCommentUser | null) => void;
}) {
  const { request, refresh, me } = useModeration();
  const [action, setAction] = useState("");
  const [moderator, setModerator] = useState<ThreadFSCommentUser | null>(null);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  const load = useCallback(
    (limit: number, offset: number) =>
      request((ctx) =>
        listActions(ctx, {
          action: action || undefined,
          moderator: moderator?.id,
          target: target?.id,
          since: toIso(since),
          until: toIso(until),
          limit,
          offset,
        }),
      ),
    [request, action, moderator, target, since, until],
  );
  const list = usePagedList<ModerationAction>(load);
  const isFiltered = Boolean(action || moderator || target || since || until);

  async function undo(batch: NonNullable<ModerationAction["batch"]>) {
    const confirmed = window.confirm(
      `Undo this batch of ${batch.comment_count} comments? Any that changed since will be left alone.`,
    );
    if (!confirmed) return;

    if (await list.run(() => request((ctx) => undoBatch(ctx, batch.id)))) {
      list.reload();
      refresh();
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-2 @xl:grid-cols-3">
        <ChoiceSelect
          label="Filter by action"
          value={action}
          onChange={setAction}
          options={LOG_ACTIONS}
        />
        <UserPicker
          label="Moderator"
          placeholder="By moderator"
          value={moderator}
          onChange={setModerator}
        />
        <UserPicker
          label="Target user"
          placeholder="Against user"
          value={target}
          onChange={onTarget}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="text-muted-foreground flex items-center gap-2 text-sm">
          From
          <Input
            value={since}
            onChange={(event) => setSince(event.target.value)}
            type="datetime-local"
            className="w-52 md:text-sm dark:scheme-dark"
          />
        </label>
        <label className="text-muted-foreground flex items-center gap-2 text-sm">
          To
          <Input
            value={until}
            onChange={(event) => setUntil(event.target.value)}
            type="datetime-local"
            className="w-52 md:text-sm dark:scheme-dark"
          />
        </label>
        <ListStatus
          list={list as PagedList<unknown>}
          label={list.total === 1 ? "entry" : "entries"}
        />
      </div>

      <ListBody
        list={list}
        empty={isFiltered ? "No entries match" : "Nothing logged yet"}
      >
        <Card className="gap-0 py-0">
          {list.items.map((entry, index) => {
            const Icon = ACTION_ICONS[entry.action] ?? ShieldCheck;

            return (
              <article key={entry.id}>
                {index > 0 && <Separator />}
                <div className="flex gap-3 p-3 text-sm">
                  <span className="bg-muted text-muted-foreground flex size-7 shrink-0 items-center justify-center rounded-full">
                    <Icon className="size-3.5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-1.5">
                      <UserLink user={entry.moderator} />
                      <span>
                        <ActionText {...entry} />
                      </span>
                      <CommentTimestamp value={entry.created_at} />
                    </div>
                    {entry.reason && (
                      <p className="text-muted-foreground mt-0.5">
                        {entry.reason}
                      </p>
                    )}
                    <ActionSubject entry={entry} />
                  </div>
                  {entry.batch &&
                    entry.action !== "undo_batch" &&
                    (entry.batch.undone_at ? (
                      <Badge variant="outline">Undone</Badge>
                    ) : (
                      me?.staff_role === "admin" && (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={list.isBusy}
                          className="hover:cursor-pointer"
                          onClick={() => void undo(entry.batch!)}
                        >
                          Undo
                        </Button>
                      )
                    ))}
                </div>
              </article>
            );
          })}
        </Card>
      </ListBody>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-muted/50 rounded-lg p-2 text-center">
      <p className="text-lg font-semibold">{value}</p>
      <p className="text-muted-foreground text-xs">{label}</p>
    </div>
  );
}

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Everything moderators know about one user, and what they can do about them. */
export function UserPanel({
  user,
  onClose,
}: {
  user: ThreadFSCommentUser | null;
  onClose: () => void;
}) {
  return (
    <Sheet
      open={Boolean(user)}
      onOpenChange={(isOpen) => {
        if (!isOpen) onClose();
      }}
    >
      {/* Portalled out of the widget, so it needs the root class for its font */}
      <SheetContent className="threadfs-root gap-0 overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-md">
        {user && <UserDetails key={user.id} user={user} />}
      </SheetContent>
    </Sheet>
  );
}

function UserDetails({ user }: { user: ThreadFSCommentUser }) {
  const {
    request,
    refresh,
    showUserComments,
    showUserLog,
    authorProfileUrl,
    me,
  } = useModeration();
  const [record, setRecord] = useState<ModerationUserDetail | null>(null);
  const [comments, setComments] = useState<ModerationComment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const [banDays, setBanDays] = useState("7");
  const [banReason, setBanReason] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [removeCount, setRemoveCount] = useState<number | null>(null);
  const [removeRefused, setRemoveRefused] = useState<string | null>(null);
  const [reasonKey, setReasonKey] = useState("");

  const load = useCallback(async () => {
    const [nextRecord, page] = await request((ctx) =>
      Promise.all([
        getUser(ctx, user.id),
        searchComments(ctx, {
          communityUserId: user.id,
          limit: 5,
          offset: 0,
        }),
      ]),
    );
    setRecord(nextRecord);
    setComments(page.items);
  }, [request, user.id]);

  useEffect(() => {
    load().catch((err: unknown) =>
      setError(errorMessage(err, "Failed to load user")),
    );
  }, [load]);

  // Notes pass false: only what changes the lists behind this panel should reload them
  async function act(work: () => Promise<unknown>, refreshLists = true) {
    try {
      setIsBusy(true);
      setError(null);
      await work();
      await load();
      if (refreshLists) refresh();
      return true;
    } catch (err: unknown) {
      setError(errorMessage(err, "Action failed"));
      return false;
    } finally {
      setIsBusy(false);
    }
  }

  async function ban(event: FormEvent) {
    event.preventDefault();

    const ok = await act(() =>
      request((ctx) =>
        banUser(ctx, {
          communityUserId: user.id,
          reason: banReason.trim() || null,
          expiresAt: banExpiry(banDays),
        }),
      ),
    );
    if (ok) setBanReason("");
  }

  async function submitNote(event: FormEvent) {
    event.preventDefault();

    const ok = await act(
      () => request((ctx) => addNote(ctx, user.id, noteBody.trim())),
      false,
    );
    if (ok) setNoteBody("");
  }

  async function previewRemoveAll() {
    try {
      setError(null);
      const { matched, refused } = await request((ctx) =>
        batchComments(ctx, {
          action: "hide",
          filters: { communityUserId: user.id },
          dryRun: true,
        }),
      );
      setRemoveCount(matched);
      setRemoveRefused(refused ?? null);
    } catch (err: unknown) {
      setError(errorMessage(err, "Action failed"));
    }
  }

  async function removeAll() {
    const ok = await act(() =>
      request((ctx) =>
        batchComments(ctx, {
          action: "hide",
          filters: { communityUserId: user.id },
          reasonKey: reasonKey || null,
        }),
      ),
    );
    if (ok) setRemoveCount(null);
  }

  const activeBan = record?.bans.find(isBanActive) ?? null;
  const banBlocked = record ? banBlockedReason(me, record) : null;
  const profileUrl = authorProfileUrl?.(user);

  return (
    <>
      <SheetHeader className="flex-row items-center gap-3 pr-12">
        <UserAvatar user={user} size="lg" />
        <div className="min-w-0">
          <SheetTitle className="flex items-center gap-2 text-base">
            <span className="truncate">{userName(user)}</span>
            {record && <StaffBadge user={record} />}
          </SheetTitle>
          <SheetDescription className="truncate text-xs">
            {user.external_user_id}
            {record &&
              ` · First seen ${new Date(record.created_at).toLocaleDateString()}`}
          </SheetDescription>
          {profileUrl && (
            <a
              href={profileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-tfs-brand-strong dark:text-tfs-brand text-xs hover:underline"
            >
              View profile
            </a>
          )}
        </div>
      </SheetHeader>

      <div className="space-y-5 px-4 pb-6">
        {error && <ErrorNote>{error}</ErrorNote>}

        {!record ? (
          !error && <ListSkeleton />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2">
              <Stat label="Comments" value={record.comment_count} />
              <Stat label="Removed" value={record.removed_count} />
              <Stat label="Reports" value={record.report_count} />
            </div>

            <Section title="Ban">
              {activeBan ? (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-rose-500/10 p-3 text-sm">
                  <div className="min-w-0">
                    <Badge variant="destructive">Banned</Badge>
                    <p className="text-muted-foreground mt-1 text-xs">
                      {banTerm(activeBan)}
                    </p>
                    {activeBan.reason && <p>{activeBan.reason}</p>}
                  </div>
                  {canLiftBan(me, record) && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={isBusy}
                      className="hover:cursor-pointer"
                      onClick={() =>
                        void act(() =>
                          request((ctx) => liftBan(ctx, activeBan.id)),
                        )
                      }
                    >
                      Lift ban
                    </Button>
                  )}
                </div>
              ) : banBlocked ? (
                <p className="text-muted-foreground text-sm">{banBlocked}</p>
              ) : (
                <form onSubmit={ban} className="flex flex-wrap gap-2">
                  <Input
                    value={banReason}
                    onChange={(event) => setBanReason(event.target.value)}
                    aria-label="Ban reason"
                    placeholder="Reason (optional)"
                    maxLength={1000}
                    className="min-w-32 flex-1 md:text-sm"
                  />
                  <BanLengthSelect
                    value={banDays}
                    onChange={setBanDays}
                    className="w-28"
                  />
                  <Button
                    type="submit"
                    variant="destructive"
                    disabled={isBusy}
                    className="hover:cursor-pointer"
                  >
                    Ban
                  </Button>
                </form>
              )}
            </Section>

            <Section title="Private notes">
              <form onSubmit={submitNote} className="flex gap-2">
                <Input
                  value={noteBody}
                  onChange={(event) => setNoteBody(event.target.value)}
                  aria-label="New note"
                  placeholder="Only moderators see this"
                  maxLength={2000}
                  className="md:text-sm"
                />
                <Button
                  type="submit"
                  variant="outline"
                  disabled={isBusy || !noteBody.trim()}
                  className="hover:cursor-pointer"
                >
                  Add
                </Button>
              </form>
              {record.notes.map((note) => (
                <div
                  key={note.id}
                  className="bg-muted/50 rounded-lg p-3 text-sm"
                >
                  <p className="wrap-break-word whitespace-pre-wrap">
                    {note.body}
                  </p>
                  <div className="text-muted-foreground mt-1 flex items-center gap-2 text-xs">
                    <span>{userName(note.author)}</span>
                    <CommentTimestamp value={note.created_at} />
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() =>
                        void act(
                          () => request((ctx) => deleteNote(ctx, note.id)),
                          false,
                        )
                      }
                      className="ml-auto hover:cursor-pointer hover:text-rose-500 hover:underline"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </Section>

            <Section
              title="Recent comments"
              action={
                <span className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => showUserLog(user)}
                    className="text-tfs-brand-strong dark:text-tfs-brand text-xs hover:cursor-pointer hover:underline"
                  >
                    View log
                  </button>
                  <button
                    type="button"
                    onClick={() => showUserComments(user)}
                    className="text-tfs-brand-strong dark:text-tfs-brand text-xs hover:cursor-pointer hover:underline"
                  >
                    View all
                  </button>
                </span>
              }
            >
              {comments.length === 0 && (
                <p className="text-muted-foreground text-sm">No comments</p>
              )}
              {comments.map((comment) => (
                <div
                  key={comment.id}
                  className="bg-muted/50 rounded-lg p-3 text-sm"
                >
                  <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
                    <CommentTimestamp value={comment.created_at} />
                    {comment.status === "hidden" && (
                      <Badge variant="destructive">Removed</Badge>
                    )}
                    {comment.status === "deleted" && (
                      <Badge variant="secondary">Deleted</Badge>
                    )}
                    <span className="min-w-0 truncate">
                      {comment.thread?.title || comment.thread?.unique_id}
                    </span>
                  </div>
                  {comment.status !== "deleted" && (
                    <div className="mt-1 line-clamp-3 [&_*]:mb-0">
                      {comment.gif && <GifLabel />}
                      <MarkdownContent markdown={comment.content} />
                    </div>
                  )}
                </div>
              ))}
            </Section>

            {removeCount === null ? (
              <Button
                type="button"
                variant="destructive"
                className="w-full hover:cursor-pointer"
                onClick={() => void previewRemoveAll()}
              >
                Remove all their comments
              </Button>
            ) : removeCount === 0 ? (
              <p className="text-muted-foreground text-sm">
                They have no visible comments to remove
              </p>
            ) : removeRefused ? (
              <p className="text-muted-foreground text-sm">{removeRefused}</p>
            ) : (
              <div className="space-y-2 rounded-lg bg-rose-500/10 p-3 text-sm">
                <p className="font-medium">
                  Remove {removeCount}{" "}
                  {removeCount === 1 ? "comment" : "comments"}?
                </p>
                <ReasonSelect value={reasonKey} onChange={setReasonKey} />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={isBusy}
                    className="hover:cursor-pointer"
                    onClick={() => void removeAll()}
                  >
                    Confirm
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={isBusy}
                    className="hover:cursor-pointer"
                    onClick={() => setRemoveCount(null)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            {record.bans.some((item) => !isBanActive(item)) && (
              <Section title="Past bans">
                {record.bans
                  .filter((item) => !isBanActive(item))
                  .map((item) => (
                    <div
                      key={item.id}
                      className="bg-muted/50 rounded-lg p-3 text-sm"
                    >
                      <p className="text-muted-foreground text-xs">
                        {banTerm(item)}
                      </p>
                      {item.reason && <p>{item.reason}</p>}
                    </div>
                  ))}
              </Section>
            )}
          </>
        )}
      </div>
    </>
  );
}
