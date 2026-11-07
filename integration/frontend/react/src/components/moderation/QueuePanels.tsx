import { Flag, Search, SlidersHorizontal, Trash2 } from "lucide-react";
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import {
  batchComments,
  listReports,
  reopenReports,
  resolveReports,
  searchComments,
  type CommentSort,
  type ReportSort,
} from "../../lib/moderationApi";
import type {
  CommentFilters,
  CommentReport,
  ModerationComment,
  ReportedComment,
  ThreadFSCommentUser,
  ThreadFSReason,
  ThreadFSThread,
} from "../../lib/types";
import { cn } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Collapsible, CollapsibleContent } from "../ui/collapsible";
import { Input } from "../ui/input";
import { CommentRow } from "./CommentRow";
import { ListStatus } from "./ListStatus";
import {
  brandButtonClass,
  ChoiceSelect,
  errorMessage,
  ErrorNote,
  ListBody,
  MAX_REMOVAL_DETAIL,
  OTHER_REASON,
  OtherReasonInput,
  ReasonSelect,
  useModeration,
  usePagedList,
  UserLink,
  type PagedList,
} from "./shared";
import { UserPicker } from "./UserPicker";

function useSelection(ids: string[]) {
  const [ticked, setSelected] = useState<Set<string>>(new Set());
  // Filters can take a ticked comment off the list, and actions mustn't reach what isn't on screen
  const selected = new Set(ids.filter((id) => ticked.has(id)));

  return {
    selected,
    isAllSelected: ids.length > 0 && ids.every((id) => selected.has(id)),
    toggle(id: string, isOn: boolean) {
      setSelected((current) => {
        const next = new Set(current);
        if (isOn) next.add(id);
        else next.delete(id);
        return next;
      });
    },
    setAll: (isOn: boolean) => setSelected(new Set(isOn ? ids : [])),
    clear: () => setSelected(new Set()),
  };
}

// As a bulk removal's reason: each comment takes its own reports' reason
const EACH_REPORT = "__each_report";

/** Acts on the ticked comments at once, offering only what applies to them. */
function SelectionBar({
  selection,
  list,
  statusOf,
  reasonOf,
  detailOf,
  onDismiss,
}: {
  selection: ReturnType<typeof useSelection>;
  list: PagedList<unknown>;
  statusOf: (id: string) => string | undefined;
  /** A comment's own reason, where it has one. */
  reasonOf?: (id: string) => string;
  /** What a comment's own Other reason tells its author. */
  detailOf?: (id: string) => string;
  onDismiss?: (ids: string[]) => Promise<unknown>;
}) {
  const { request, syncOpenReports } = useModeration();
  const [reasonKey, setReasonKey] = useState(reasonOf ? EACH_REPORT : "");
  const [reasonDetail, setReasonDetail] = useState("");
  const isOther = reasonKey === OTHER_REASON;
  const ids = [...selection.selected];
  const removable = ids.filter((id) => statusOf(id) === "visible");
  const restorable = ids.filter((id) => statusOf(id) === "hidden");

  async function finish(work: () => Promise<unknown>) {
    if (await list.run(work)) {
      selection.clear();
      list.reload();
      syncOpenReports();
    }
  }

  const restore = (targets: string[]) =>
    finish(() =>
      request((ctx) =>
        batchComments(ctx, {
          action: "restore",
          commentIds: targets.map(Number),
        }),
      ),
    );

  function remove(targets: string[]) {
    // A batch takes one reason, so comments go in a batch per reason and wording
    const batches = new Map<
      string,
      { key: string; detail: string; commentIds: number[] }
    >();

    for (const id of targets) {
      const isEach = reasonKey === EACH_REPORT;
      let key = isEach ? reasonOf!(id) : reasonKey;
      let detail = "";

      if (key === OTHER_REASON) {
        detail = isEach ? (detailOf?.(id) ?? "") : reasonDetail.trim();
        // An old report may not say why, and Other can't go to the author empty
        if (!detail) key = "";
      }

      const batchKey = JSON.stringify([key, detail]);
      const batch = batches.get(batchKey) ?? { key, detail, commentIds: [] };
      batch.commentIds.push(Number(id));
      batches.set(batchKey, batch);
    }

    return finish(() =>
      request((ctx) =>
        Promise.all(
          [...batches.values()].map(({ key, detail, commentIds }) =>
            batchComments(ctx, {
              action: "hide",
              commentIds,
              reasonKey: key || null,
              reasonDetail: detail || null,
            }),
          ),
        ),
      ),
    );
  }

  return (
    <div
      className={cn(
        "flex min-h-11 flex-wrap items-center gap-2 rounded-lg px-4 py-1.5 text-sm",
        ids.length > 0 && "bg-muted sticky top-0 z-10",
      )}
    >
      <label className="flex items-center gap-3 hover:cursor-pointer">
        <Checkbox
          checked={selection.isAllSelected}
          onCheckedChange={(checked) => selection.setAll(checked === true)}
        />
        {ids.length ? `${ids.length} selected` : "Select all on this page"}
      </label>

      {ids.length > 0 && (
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {removable.length > 0 && (
            <>
              <ReasonSelect
                value={reasonKey}
                onChange={setReasonKey}
                extraOptions={
                  reasonOf
                    ? [{ value: EACH_REPORT, label: "Each report's reason" }]
                    : []
                }
                className="w-48"
              />
              {isOther && (
                <OtherReasonInput
                  value={reasonDetail}
                  onChange={setReasonDetail}
                  className="w-64"
                />
              )}
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={list.isBusy || (isOther && !reasonDetail.trim())}
                className="hover:cursor-pointer"
                onClick={() => void remove(removable)}
              >
                Remove {removable.length}
              </Button>
            </>
          )}
          {restorable.length > 0 && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={list.isBusy}
              className="hover:cursor-pointer"
              onClick={() => void restore(restorable)}
            >
              Restore {restorable.length}
            </Button>
          )}
          {onDismiss && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={list.isBusy}
              className="hover:cursor-pointer"
              onClick={() => void finish(() => onDismiss(ids))}
            >
              Dismiss {ids.length}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/** The closed reports in a group, one per outcome: several closed together read as one. */
function reportOutcomes(reports: CommentReport[]) {
  const outcomes = new Map<string, CommentReport>();

  for (const report of reports) {
    if (report.status === "open") continue;
    const key = `${report.status}:${report.resolver?.id}`;
    if (!outcomes.has(key)) outcomes.set(key, report);
  }

  return [...outcomes.values()];
}

/** The reason a reported comment's removal starts on: its most reported one still on the community's list. */
/** What the latest Other report said, as a start for telling the author. Older reports could run longer. */
function reportedDetail(reports: CommentReport[]) {
  const report = reports.find(
    ({ reason, details }) => reason === OTHER_REASON && details,
  );
  return report?.details?.slice(0, MAX_REMOVAL_DETAIL) ?? "";
}

function likelyReason(reports: CommentReport[], known: ThreadFSReason[]) {
  const counts = new Map<string, number>();

  for (const report of reports) {
    if (known.some(({ key }) => key === report.reason)) {
      counts.set(report.reason, (counts.get(report.reason) ?? 0) + 1);
    }
  }

  // Reports arrive newest first and a sort keeps ties in order, so the latest wins a tie
  return [...counts].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
}

/** The reports on a comment, one line per reason. */
function ReportSummary({ reports }: { reports: ReportedComment["reports"] }) {
  const byReason = new Map<string, typeof reports>();

  for (const report of reports) {
    const label = report.reason_label ?? report.reason;
    byReason.set(label, [...(byReason.get(label) ?? []), report]);
  }

  return (
    <ul className="mt-3 space-y-1 rounded-lg bg-rose-500/10 px-3 py-2 text-sm">
      {[...byReason].map(([label, group]) => (
        <li key={label}>
          <Flag className="mr-1.5 inline size-3.5 text-rose-500" />
          <span className="font-medium">{label}</span>
          {group.length > 1 && (
            <span className="font-medium"> ×{group.length}</span>
          )}
          <span className="text-muted-foreground">
            {" "}
            from{" "}
            {group.map((report, index) => (
              <Fragment key={report.id}>
                {index > 0 && ", "}
                <UserLink user={report.reporter} />
              </Fragment>
            ))}
          </span>
          {reportOutcomes(group).map((report) => (
            <span key={report.id} className="text-muted-foreground">
              {" "}
              · {report.status} by <UserLink user={report.resolver} />
            </span>
          ))}
          {group
            .filter((report) => report.details)
            .map((report) => (
              <p key={report.id} className="mt-1">
                {report.details}
              </p>
            ))}
        </li>
      ))}
    </ul>
  );
}

export function ReportsPanel() {
  const { request, reasons, onOpenReports, syncOpenReports } = useModeration();
  const [reportStatus, setReportStatus] = useState<"open" | "closed">("open");
  const [reason, setReason] = useState("");
  const [sort, setSort] = useState<ReportSort>("newest");
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const load = useCallback(
    (limit: number, offset: number) =>
      request((ctx) =>
        listReports(ctx, {
          status: reportStatus,
          reason: reason || undefined,
          sort,
          limit,
          offset,
        }),
      ),
    [request, reportStatus, reason, sort],
  );
  const list = usePagedList<ReportedComment>(load);
  const selection = useSelection(list.items.map((item) => item.comment.id));

  useEffect(() => {
    if (
      reportStatus === "open" &&
      !reason &&
      !list.isLoading &&
      list.total != null
    ) {
      onOpenReports(list.total);
    }
  }, [reportStatus, reason, list.isLoading, list.total, onOpenReports]);

  const findEntry = (id: string) =>
    list.items.find((item) => item.comment.id === id);

  const dismissAll = (ids: string[]) =>
    request((ctx) =>
      Promise.all(ids.map((id) => resolveReports(ctx, id, "dismissed"))),
    );

  async function dismiss(commentId: string) {
    const ok = await list.run(() => dismissAll([commentId]));

    if (ok) {
      setDismissed((current) => new Set(current).add(commentId));
      syncOpenReports();
    }
  }

  async function reopen(commentId: string) {
    const ok = await list.run(() =>
      request((ctx) => reopenReports(ctx, commentId)),
    );

    if (ok) {
      list.reload();
      syncOpenReports();
    }
  }

  const applyToComments = (
    update: (item: ModerationComment) => ModerationComment,
  ) =>
    list.setItems((items) =>
      items.map((item) => ({ ...item, comment: update(item.comment) })),
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <ChoiceSelect
          label="Report status"
          value={reportStatus}
          onChange={(value) => setReportStatus(value as "open" | "closed")}
          className="w-28"
          options={[
            { value: "open", label: "Open" },
            { value: "closed", label: "Closed" },
          ]}
        />
        <ChoiceSelect
          label="Filter by reason"
          value={reason}
          onChange={setReason}
          className="w-44"
          options={[
            { value: "", label: "Any reason" },
            ...reasons.map(({ key, label }) => ({ value: key, label })),
          ]}
        />
        <ChoiceSelect
          label="Sort reports"
          value={sort}
          onChange={(value) => setSort(value as ReportSort)}
          className="w-40"
          options={[
            { value: "newest", label: "Newest report" },
            { value: "oldest", label: "Oldest report" },
            { value: "most_reported", label: "Most reported" },
          ]}
        />
        <ListStatus list={list as PagedList<unknown>} label={reportStatus} />
      </div>

      {list.items.length > 0 && (
        <SelectionBar
          selection={selection}
          list={list as PagedList<unknown>}
          statusOf={(id) => findEntry(id)?.comment.status}
          reasonOf={(id) => likelyReason(findEntry(id)?.reports ?? [], reasons)}
          detailOf={(id) => reportedDetail(findEntry(id)?.reports ?? [])}
          onDismiss={reportStatus === "open" ? dismissAll : undefined}
        />
      )}

      <ListBody list={list} empty={`No ${reportStatus} reports`} icon={Flag}>
        {list.items.map(({ comment, reports }) => (
          <CommentRow
            key={comment.id}
            comment={comment}
            run={list.run}
            onChange={applyToComments}
            isSelected={selection.selected.has(comment.id)}
            onSelect={(isOn) => selection.toggle(comment.id, isOn)}
            defaultReasonKey={likelyReason(reports, reasons)}
            defaultReasonDetail={reportedDetail(reports)}
            extraActions={
              comment.status === "visible" &&
              (reportStatus === "closed" ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="hover:cursor-pointer"
                  disabled={list.isBusy}
                  onClick={() => void reopen(comment.id)}
                >
                  Reopen
                </Button>
              ) : dismissed.has(comment.id) ? (
                <Badge variant="secondary">Dismissed</Badge>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="hover:cursor-pointer"
                  disabled={list.isBusy}
                  onClick={() => void dismiss(comment.id)}
                >
                  Dismiss
                </Button>
              ))
            }
          >
            <ReportSummary reports={reports} />
          </CommentRow>
        ))}
      </ListBody>
    </div>
  );
}

// As a Removed filter: comments removed without a reason
const NO_REASON = "__no_reason";

export function RemovedPanel() {
  const { request, reasons } = useModeration();
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [author, setAuthor] = useState<ThreadFSCommentUser | null>(null);
  const [moderator, setModerator] = useState<ThreadFSCommentUser | null>(null);
  const [removalReason, setRemovalReason] = useState("");
  const [sort, setSort] = useState<CommentSort>("changed");

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(text.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [text]);

  const filters = useMemo<CommentFilters>(
    () => ({
      communityUserId: author?.id,
      removedBy: moderator?.id,
      removalReason:
        removalReason === NO_REASON ? undefined : removalReason || undefined,
      withoutRemovalReason: removalReason === NO_REASON || undefined,
    }),
    [author, moderator, removalReason],
  );

  const load = useCallback(
    (limit: number, offset: number) =>
      request((ctx) =>
        searchComments(ctx, {
          ...filters,
          status: "hidden",
          q: search,
          sort,
          limit,
          offset,
        }),
      ),
    [request, filters, search, sort],
  );
  const list = usePagedList<ModerationComment>(load);
  const selection = useSelection(list.items.map((item) => item.id));
  const isFiltered = Boolean(search) || Object.values(filters).some(Boolean);

  return (
    <div className="space-y-3">
      <div className="grid gap-2 @xl:grid-cols-4">
        <div className="relative">
          <Search className="text-muted-foreground absolute top-2 left-2.5 size-4" />
          <Input
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-label="Search text"
            placeholder="Search comments"
            className="pl-8 md:text-sm"
          />
        </div>
        <UserPicker
          label="Author"
          placeholder="Filter by author"
          value={author}
          onChange={setAuthor}
        />
        <UserPicker
          label="Removed by"
          placeholder="Removed by"
          value={moderator}
          onChange={setModerator}
        />
        <ChoiceSelect
          label="Filter by reason"
          value={removalReason}
          onChange={setRemovalReason}
          options={[
            { value: "", label: "Any reason" },
            { value: NO_REASON, label: "No reason given" },
            ...reasons.map(({ label }) => ({ value: label, label })),
          ]}
        />
      </div>

      {Object.values(filters).some(Boolean) && (
        <BatchBar
          filters={filters}
          hasTextSearch={Boolean(search)}
          restoreOnly
          onDone={list.reload}
        />
      )}

      <div className="flex items-center gap-2">
        <ChoiceSelect
          label="Sort removed comments"
          value={sort}
          onChange={(value) => setSort(value as CommentSort)}
          className="w-44"
          options={[
            { value: "changed", label: "Recently removed" },
            { value: "newest", label: "Newest comment" },
            { value: "oldest", label: "Oldest comment" },
            { value: "most_downvoted", label: "Most downvoted" },
          ]}
        />
        <ListStatus list={list as PagedList<unknown>} label="removed" />
      </div>

      {list.items.length > 0 && (
        <SelectionBar
          selection={selection}
          list={list as PagedList<unknown>}
          statusOf={(id) => list.items.find((item) => item.id === id)?.status}
        />
      )}

      <ListBody
        list={list}
        empty={
          isFiltered ? "No removed comments match" : "Nothing has been removed"
        }
        icon={Trash2}
      >
        {list.items.map((comment) => (
          <CommentRow
            key={comment.id}
            comment={comment}
            run={list.run}
            onChange={(update) => list.setItems((items) => items.map(update))}
            isSelected={selection.selected.has(comment.id)}
            onSelect={(isOn) => selection.toggle(comment.id, isOn)}
          />
        ))}
      </ListBody>
    </div>
  );
}

type SearchFields = {
  q: string;
  status: string;
  source: string;
  client: string;
  threadId: string;
  since: string;
  until: string;
};

const NO_SEARCH: SearchFields = {
  q: "",
  status: "",
  source: "",
  client: "",
  threadId: "",
  since: "",
  until: "",
};

const toIso = (local: string) =>
  local ? new Date(local).toISOString() : undefined;

export function CommentsPanel({
  userFilter,
  onUserFilter,
  threadFilter,
  onThreadFilter,
}: {
  userFilter: ThreadFSCommentUser | null;
  onUserFilter: (user: ThreadFSCommentUser | null) => void;
  threadFilter: ThreadFSThread | null;
  onThreadFilter: (thread: ThreadFSThread | null) => void;
}) {
  const { request } = useModeration();
  const [form, setForm] = useState<SearchFields>(NO_SEARCH);
  const [search, setSearch] = useState<SearchFields>(NO_SEARCH);
  const [sort, setSort] = useState<CommentSort>("newest");
  const [showFilters, setShowFilters] = useState(false);

  const filters = useMemo<CommentFilters>(
    () => ({
      source: search.source.trim() || undefined,
      client: search.client.trim() || undefined,
      threadId:
        threadFilter?.unique_id ?? (search.threadId.trim() || undefined),
      communityUserId: userFilter?.id,
      since: toIso(search.since),
      until: toIso(search.until),
    }),
    [search, userFilter, threadFilter],
  );

  const load = useCallback(
    (limit: number, offset: number) =>
      request((ctx) =>
        searchComments(ctx, {
          ...filters,
          status: search.status,
          q: search.q.trim(),
          sort,
          limit,
          offset,
        }),
      ),
    [request, filters, search.status, search.q, sort],
  );
  const list = usePagedList<ModerationComment>(load);
  const selection = useSelection(list.items.map((item) => item.id));

  function submit(event: FormEvent) {
    event.preventDefault();
    setSearch(form);
  }

  function field(key: keyof SearchFields) {
    return {
      value: form[key],
      onChange: (event: { target: { value: string } }) =>
        setForm((current) => ({ ...current, [key]: event.target.value })),
    };
  }

  const hasBatchFilter = Object.values(filters).some(Boolean);
  const moreFilterCount = [
    filters.source,
    filters.client,
    filters.threadId,
    filters.since,
    filters.until,
  ].filter(Boolean).length;

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="space-y-2">
        <div className="grid gap-2 @xl:grid-cols-[1fr_1fr_10rem_auto]">
          <div className="relative">
            <Search className="text-muted-foreground absolute top-2 left-2.5 size-4" />
            <Input
              {...field("q")}
              aria-label="Search text"
              placeholder="Search comments"
              className="pl-8 md:text-sm"
            />
          </div>
          <UserPicker
            label="User"
            placeholder="Filter by user"
            value={userFilter}
            onChange={onUserFilter}
          />
          <ChoiceSelect
            label="Status"
            value={form.status}
            onChange={(status) => {
              setForm((current) => ({ ...current, status }));
              setSearch((current) => ({ ...current, status }));
            }}
            options={[
              { value: "", label: "Any status" },
              { value: "visible", label: "Visible" },
              { value: "hidden", label: "Removed" },
              { value: "deleted", label: "Deleted by author" },
            ]}
          />
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              aria-expanded={showFilters}
              className="flex-1 hover:cursor-pointer"
              onClick={() => setShowFilters((value) => !value)}
            >
              <SlidersHorizontal /> Filters
              {moreFilterCount > 0 && ` (${moreFilterCount})`}
            </Button>
            <Button type="submit" className={cn("flex-1", brandButtonClass)}>
              Search
            </Button>
          </div>
        </div>

        <Collapsible open={showFilters}>
          <CollapsibleContent className="grid gap-2 @lg:grid-cols-3">
            <Input
              {...field("source")}
              aria-label="Source"
              placeholder="Source site"
              className="md:text-sm"
            />
            <Input
              {...field("client")}
              aria-label="Client"
              placeholder="Client (web, extension)"
              className="md:text-sm"
            />
            <Input
              {...field("threadId")}
              aria-label="Thread id"
              placeholder="Thread id"
              className="md:text-sm"
            />
            <label className="text-muted-foreground flex items-center gap-2 text-sm @lg:col-span-1">
              From
              <Input
                {...field("since")}
                type="datetime-local"
                className="md:text-sm dark:scheme-dark"
              />
            </label>
            <label className="text-muted-foreground flex items-center gap-2 text-sm">
              To
              <Input
                {...field("until")}
                type="datetime-local"
                className="md:text-sm dark:scheme-dark"
              />
            </label>
          </CollapsibleContent>
        </Collapsible>
      </form>

      {threadFilter && (
        <p className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground shrink-0">In thread:</span>
          <span className="min-w-0 truncate font-medium">
            {threadFilter.title || threadFilter.unique_id}
          </span>
          <button
            type="button"
            onClick={() => onThreadFilter(null)}
            className="text-muted-foreground shrink-0 hover:cursor-pointer hover:underline"
          >
            Clear
          </button>
        </p>
      )}

      {hasBatchFilter && (
        <BatchBar
          filters={filters}
          hasTextSearch={Boolean(search.q.trim() || search.status)}
          onDone={list.reload}
        />
      )}

      <div className="flex items-center gap-2">
        <ChoiceSelect
          label="Sort comments"
          value={sort}
          onChange={(value) => setSort(value as CommentSort)}
          className="w-44"
          options={[
            { value: "newest", label: "Newest" },
            { value: "oldest", label: "Oldest" },
            { value: "changed", label: "Recently changed" },
            { value: "most_downvoted", label: "Most downvoted" },
          ]}
        />
        <ListStatus
          list={list as PagedList<unknown>}
          label={list.total === 1 ? "comment" : "comments"}
        />
      </div>

      {list.items.length > 0 && (
        <SelectionBar
          selection={selection}
          list={list as PagedList<unknown>}
          statusOf={(id) => list.items.find((item) => item.id === id)?.status}
        />
      )}

      <ListBody list={list} empty="No comments match">
        {list.items.map((comment) => (
          <CommentRow
            key={comment.id}
            comment={comment}
            run={list.run}
            onChange={(update) => list.setItems((items) => items.map(update))}
            isSelected={selection.selected.has(comment.id)}
            onSelect={(isOn) => selection.toggle(comment.id, isOn)}
          />
        ))}
      </ListBody>
    </div>
  );
}

/** Acts on everything matching the filters, beyond the page on screen. */
function BatchBar({
  filters,
  hasTextSearch,
  restoreOnly = false,
  onDone,
}: {
  filters: CommentFilters;
  hasTextSearch: boolean;
  restoreOnly?: boolean;
  onDone: () => void;
}) {
  const { request, syncOpenReports } = useModeration();
  const [preview, setPreview] = useState<{
    action: "hide" | "restore";
    matched: number;
    refused?: string;
  } | null>(null);
  const [reasonKey, setReasonKey] = useState("");
  const [reasonDetail, setReasonDetail] = useState("");
  const [note, setNote] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const isOther = reasonKey === OTHER_REASON;

  // A preview only holds for the filters it counted
  useEffect(() => {
    setPreview(null);
    setResult(null);
  }, [filters]);

  async function attempt(work: () => Promise<void>) {
    try {
      setIsBusy(true);
      setError(null);
      setResult(null);
      await work();
    } catch (err: unknown) {
      setError(errorMessage(err, "Batch failed"));
    } finally {
      setIsBusy(false);
    }
  }

  const count = (action: "hide" | "restore") =>
    attempt(async () => {
      const { matched, refused } = await request((ctx) =>
        batchComments(ctx, { action, filters, dryRun: true }),
      );
      setPreview({ action, matched, refused });
    });

  const confirm = (action: "hide" | "restore") =>
    attempt(async () => {
      const { changed } = await request((ctx) =>
        batchComments(ctx, {
          action,
          filters,
          reasonKey: action === "hide" ? reasonKey || null : null,
          reasonDetail:
            action === "hide" && isOther ? reasonDetail.trim() : null,
          note: note.trim() || null,
        }),
      );
      setPreview(null);
      setNote("");
      setResult(
        `${action === "hide" ? "Removed" : "Restored"} ${changed} ${changed === 1 ? "comment" : "comments"}`,
      );
      onDone();
      syncOpenReports();
    });

  // The batch runs on the filters alone, so it must not look like it follows the text or status search
  if (hasTextSearch) {
    return (
      <p className="text-muted-foreground text-sm">
        Clear the text{restoreOnly ? "" : " and status"} search to act on
        everything matching these filters.
      </p>
    );
  }

  return (
    <div className="bg-muted/50 space-y-2 rounded-lg p-3 text-sm">
      {preview ? (
        preview.matched === 0 || preview.refused ? (
          <p>
            {preview.refused ??
              `No comments to ${preview.action === "hide" ? "remove" : "restore"}`}
            .{" "}
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="hover:cursor-pointer hover:underline"
            >
              Back
            </button>
          </p>
        ) : (
          <>
            <p className="font-medium">
              {preview.action === "hide" ? "Remove" : "Restore"}{" "}
              {preview.matched} {preview.matched === 1 ? "comment" : "comments"}
              ?
            </p>
            <div className="grid gap-2 @lg:grid-cols-2">
              {preview.action === "hide" && (
                <ReasonSelect value={reasonKey} onChange={setReasonKey} />
              )}
              {preview.action === "hide" && isOther && (
                <OtherReasonInput
                  value={reasonDetail}
                  onChange={setReasonDetail}
                />
              )}
              <Input
                value={note}
                onChange={(event) => setNote(event.target.value)}
                aria-label="Private note"
                placeholder="Private note (optional)"
                maxLength={1000}
                className="md:text-sm"
              />
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant={preview.action === "hide" ? "destructive" : "default"}
                disabled={
                  isBusy ||
                  (preview.action === "hide" && isOther && !reasonDetail.trim())
                }
                className="hover:cursor-pointer"
                onClick={() => void confirm(preview.action)}
              >
                Confirm
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={isBusy}
                className="hover:cursor-pointer"
                onClick={() => setPreview(null)}
              >
                Cancel
              </Button>
            </div>
          </>
        )
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground">
            Everything matching these filters:
          </span>
          {!restoreOnly && (
            <Button
              type="button"
              size="sm"
              variant="destructive"
              disabled={isBusy}
              className="hover:cursor-pointer"
              onClick={() => void count("hide")}
            >
              Remove
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={isBusy}
            className="hover:cursor-pointer"
            onClick={() => void count("restore")}
          >
            Restore
          </Button>
          {result && <span>{result}</span>}
        </div>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
    </div>
  );
}
