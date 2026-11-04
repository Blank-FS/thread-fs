import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useState } from "react";
import { replaceReasons } from "../../lib/moderationApi";
import type { ThreadFSReason } from "../../lib/types";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import {
  brandButtonClass,
  errorMessage,
  ErrorNote,
  useModeration,
} from "./shared";

function slug(label: string) {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 56);
}

/** Gives each new reason a key. Existing keys never change, so past reports stay tied to their reason. */
function withKeys(reasons: ThreadFSReason[]): ThreadFSReason[] {
  const taken = new Set(reasons.map(({ key }) => key).filter(Boolean));

  return reasons.map(({ key, label }) => {
    if (key) return { key, label: label.trim() };

    const base = slug(label) || "reason";
    let next = base;
    for (let n = 2; taken.has(next); n++) next = `${base}_${n}`;
    taken.add(next);

    return { key: next, label: label.trim() };
  });
}

/** Admins only: the community's reasons, for reporting and removing comments. */
export function SettingsPanel() {
  const { request, reasons, setReasons } = useModeration();
  const [draft, setDraft] = useState(reasons);
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function change(next: ThreadFSReason[]) {
    setDraft(next);
    setIsSaved(false);
  }

  function move(index: number, by: number) {
    const next = [...draft];
    const [reason] = next.splice(index, 1);
    next.splice(index + by, 0, reason);
    change(next);
  }

  async function save() {
    try {
      setIsSaving(true);
      setError(null);
      const saved = await request((ctx) =>
        replaceReasons(ctx, withKeys(draft)),
      );
      setReasons(saved);
      setDraft(saved);
      setIsSaved(true);
    } catch (err: unknown) {
      setError(errorMessage(err, "Failed to save"));
    } finally {
      setIsSaving(false);
    }
  }

  const isValid =
    draft.length > 0 && draft.every(({ label }) => label.trim().length > 0);

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold">Reasons</h3>
        <p className="text-muted-foreground text-sm">
          Readers choose from these when reporting a comment, and moderators
          when removing one. The author of a removed comment sees the reason.
          Past reports and removals keep the wording they were made with.
        </p>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}

      <Card className="gap-2 p-3">
        {draft.map((reason, index) => (
          <div
            key={reason.key || `new-${index}`}
            className="flex items-center gap-1"
          >
            <Input
              value={reason.label}
              onChange={(event) =>
                change(
                  draft.map((item, position) =>
                    position === index
                      ? { ...item, label: event.target.value }
                      : item,
                  ),
                )
              }
              aria-label={`Reason ${index + 1}`}
              placeholder="Reason"
              maxLength={128}
              className="flex-1 md:text-sm"
            />
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              aria-label="Move up"
              disabled={index === 0}
              className="hover:cursor-pointer"
              onClick={() => move(index, -1)}
            >
              <ArrowUp />
            </Button>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              aria-label="Move down"
              disabled={index === draft.length - 1}
              className="hover:cursor-pointer"
              onClick={() => move(index, 1)}
            >
              <ArrowDown />
            </Button>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              aria-label="Delete reason"
              className="hover:cursor-pointer"
              onClick={() =>
                change(draft.filter((_, position) => position !== index))
              }
            >
              <X />
            </Button>
          </div>
        ))}
      </Card>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={draft.length >= 20}
          className="hover:cursor-pointer"
          onClick={() => change([...draft, { key: "", label: "" }])}
        >
          <Plus /> Add reason
        </Button>
        {isSaved && (
          <span className="text-muted-foreground text-sm">Saved</span>
        )}
        <Button
          type="button"
          disabled={!isValid || isSaving}
          className={`ml-auto ${brandButtonClass}`}
          onClick={() => void save()}
        >
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}
