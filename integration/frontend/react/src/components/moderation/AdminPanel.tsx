import { useEffect, useState, type FormEvent } from "react";
import {
  getAdminOverview,
  updateLimits,
  updateRulesUrl,
} from "../../lib/moderationApi";
import type { AdminOverview, StaffActivity } from "../../lib/types";
import CommentTimestamp from "../card/CommentTimestamp";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Separator } from "../ui/separator";
import { SettingsPanel } from "./SettingsPanel";
import {
  brandButtonClass,
  errorMessage,
  ErrorNote,
  ListSkeleton,
  StaffBadge,
  useModeration,
  UserAvatar,
  UserLink,
} from "./shared";

function Heading({ title, children }: { title: string; children: string }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-muted-foreground text-sm">{children}</p>
    </div>
  );
}

function plural(count: number, one: string, many: string) {
  return `${count} ${count === 1 ? one : many}`;
}

function StaffRow({ row, days }: { row: StaffActivity; days: number }) {
  const { user, removed, restored, bans, batches } = row;
  const activity = [
    removed && `${removed} removed`,
    restored && `${restored} restored`,
    bans && plural(bans, "ban", "bans"),
    batches && plural(batches, "batch", "batches"),
  ].filter(Boolean);

  return (
    <div className="flex items-center gap-3 p-3 text-sm">
      <UserAvatar user={user} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <UserLink user={user} />
          <StaffBadge user={user} />
          {row.is_suspended && <Badge variant="destructive">Suspended</Badge>}
        </div>
        <p className="text-muted-foreground mt-0.5">
          {activity.length
            ? activity.join(" · ")
            : `No activity in the last ${days} days`}
        </p>
      </div>
      {row.last_active_at && <CommentTimestamp value={row.last_active_at} />}
    </div>
  );
}

function LimitsForm({
  overview,
  onSaved,
}: {
  overview: AdminOverview;
  onSaved: (overview: AdminOverview) => void;
}) {
  const { request, refresh } = useModeration();
  const [batchSize, setBatchSize] = useState(String(overview.max_batch_size));
  const [daily, setDaily] = useState(String(overview.max_daily_batch_changes));
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const batchNumber = Number(batchSize);
  const dailyNumber = Number(daily);
  const isValid =
    Number.isInteger(batchNumber) &&
    Number.isInteger(dailyNumber) &&
    batchNumber >= 1 &&
    batchNumber <= 1000 &&
    dailyNumber >= batchNumber &&
    dailyNumber <= 100000;

  async function save(event: FormEvent) {
    event.preventDefault();

    try {
      setIsSaving(true);
      setError(null);
      onSaved(
        await request((ctx) =>
          updateLimits(ctx, {
            maxBatchSize: batchNumber,
            maxDailyBatchChanges: dailyNumber,
          }),
        ),
      );
      setIsSaved(true);
      refresh();
    } catch (err: unknown) {
      setError(errorMessage(err, "Failed to save"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void save(event)} className="space-y-3">
      {error && <ErrorNote>{error}</ErrorNote>}
      <Card className="gap-3 p-3 @lg:flex-row">
        <label className="flex-1 space-y-1 text-sm">
          <span>Comments per batch</span>
          <Input
            type="number"
            inputMode="numeric"
            min={1}
            max={1000}
            value={batchSize}
            onChange={(event) => {
              setBatchSize(event.target.value);
              setIsSaved(false);
            }}
          />
        </label>
        <label className="flex-1 space-y-1 text-sm">
          <span>Comments per day</span>
          <Input
            type="number"
            inputMode="numeric"
            min={1}
            max={100000}
            value={daily}
            onChange={(event) => {
              setDaily(event.target.value);
              setIsSaved(false);
            }}
          />
        </label>
      </Card>
      <div className="flex items-center gap-2">
        {!isValid && (
          <span className="text-muted-foreground text-sm">
            The daily limit can't be lower than the batch limit
          </span>
        )}
        {isSaved && (
          <span className="text-muted-foreground text-sm">Saved</span>
        )}
        <Button
          type="submit"
          disabled={!isValid || isSaving}
          className={`ml-auto ${brandButtonClass}`}
        >
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>
    </form>
  );
}

// Where the comment widget's Rules button links: the community's rules, on its own site
function RulesForm({
  overview,
  onSaved,
}: {
  overview: AdminOverview;
  onSaved: (overview: AdminOverview) => void;
}) {
  const { request, refresh } = useModeration();
  const [url, setUrl] = useState(overview.rules_url ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = url.trim();
  const isValid = trimmed === "" || /^https?:\/\/\S+$/.test(trimmed);

  async function save(event: FormEvent) {
    event.preventDefault();

    try {
      setIsSaving(true);
      setError(null);
      onSaved(await request((ctx) => updateRulesUrl(ctx, trimmed)));
      setIsSaved(true);
      refresh();
    } catch (err: unknown) {
      setError(errorMessage(err, "Failed to save"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void save(event)} className="space-y-3">
      {error && <ErrorNote>{error}</ErrorNote>}
      <Card className="p-3">
        <label className="space-y-1 text-sm">
          <span>Rules page</span>
          <Input
            type="url"
            inputMode="url"
            placeholder="https://example.com/comment-rules"
            value={url}
            onChange={(event) => {
              setUrl(event.target.value);
              setIsSaved(false);
            }}
          />
        </label>
      </Card>
      <div className="flex items-center gap-2">
        {!isValid && (
          <span className="text-muted-foreground text-sm">
            Use a full web address, starting with https://
          </span>
        )}
        {isSaved && (
          <span className="text-muted-foreground text-sm">Saved</span>
        )}
        <Button
          type="submit"
          disabled={!isValid || isSaving}
          className={`ml-auto ${brandButtonClass}`}
        >
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>
    </form>
  );
}

/** Admins only: how the staff are doing, and the community's moderation settings. */
export function AdminPanel() {
  const { request, version } = useModeration();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;

    request(getAdminOverview)
      .then((next) => {
        if (isCurrent) setOverview(next);
      })
      .catch((err: unknown) => {
        if (isCurrent) setError(errorMessage(err, "Failed to load"));
      });

    return () => {
      isCurrent = false;
    };
  }, [request, version]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!overview) return <ListSkeleton />;

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <Heading title="Staff">
          {`Who has a role here, and what they've done in the last ${overview.activity_days} days. Staff appear once they've visited with their role.`}
        </Heading>
        {overview.staff.length ? (
          <Card className="gap-0 py-0">
            {overview.staff.map((row, index) => (
              <div key={row.user.id}>
                {index > 0 && <Separator />}
                <StaffRow row={row} days={overview.activity_days} />
              </div>
            ))}
          </Card>
        ) : (
          <p className="text-muted-foreground text-sm">No staff yet</p>
        )}
      </section>

      <section className="space-y-3">
        <Heading title="Moderator limits">
          How many comments a moderator can remove or restore in bulk. Clearing
          out one regular user isn't limited, and neither are admins.
        </Heading>
        <LimitsForm overview={overview} onSaved={setOverview} />
      </section>

      <section className="space-y-3">
        <Heading title="Comment rules">
          The page with your community&apos;s rules. The comment box&apos;s
          Rules button links to it. Leave it empty for a short default instead.
        </Heading>
        <RulesForm overview={overview} onSaved={setOverview} />
      </section>

      <section>
        <SettingsPanel />
      </section>

      <section className="space-y-3">
        <Heading title="Allowed origins">
          The sites this community's widgets can run on. These are set when the
          community is configured, not here.
        </Heading>
        <Card className="gap-1 p-3 text-sm">
          {overview.origins.map((origin) => (
            <code key={origin} className="break-all">
              {origin}
            </code>
          ))}
        </Card>
      </section>
    </div>
  );
}
