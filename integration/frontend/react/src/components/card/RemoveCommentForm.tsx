import { useState, type FormEvent } from "react";
import type { CommentRemoval } from "../../lib/moderationApi";
import type { ThreadFSReason } from "../../lib/types";
import {
  banExpiry,
  BanLengthSelect,
  ChoiceSelect,
  errorMessage,
  OTHER_REASON,
  OtherReasonInput,
} from "../moderation/shared";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";

/** A moderator's removal of a comment, where it sits in the thread. */
export default function RemoveCommentForm({
  authorName,
  reasons,
  onRemove,
  onCancel,
}: {
  authorName: string;
  reasons: ThreadFSReason[];
  onRemove: (removal: CommentRemoval) => Promise<void>;
  onCancel: () => void;
}) {
  const [reasonKey, setReasonKey] = useState("");
  const [reasonDetail, setReasonDetail] = useState("");
  const [note, setNote] = useState("");
  const [alsoBan, setAlsoBan] = useState(false);
  const [banDays, setBanDays] = useState("7");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOther = reasonKey === OTHER_REASON;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    try {
      setIsBusy(true);
      setError(null);
      await onRemove({
        reasonKey: reasonKey || null,
        reasonDetail: isOther ? reasonDetail.trim() : null,
        note: note.trim() || null,
        ban: alsoBan,
        banExpiresAt: alsoBan ? banExpiry(banDays) : null,
      });
    } catch (err: unknown) {
      setError(errorMessage(err, "Failed to remove comment"));
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <form
      className="bg-muted/50 mt-3 space-y-3 rounded-lg p-3"
      onSubmit={(event) => void handleSubmit(event)}
    >
      <ChoiceSelect
        label="Reason shown to the author"
        value={reasonKey}
        onChange={setReasonKey}
        options={[
          { value: "", label: "No reason given" },
          ...reasons.map(({ key, label }) => ({ value: key, label })),
        ]}
      />
      {isOther && (
        <OtherReasonInput value={reasonDetail} onChange={setReasonDetail} />
      )}
      <Input
        value={note}
        onChange={(event) => setNote(event.target.value)}
        aria-label="Private note"
        placeholder="Private note (optional)"
        maxLength={1000}
        className="md:text-sm"
      />
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm hover:cursor-pointer">
          <Checkbox
            checked={alsoBan}
            onCheckedChange={(checked) => setAlsoBan(checked === true)}
          />
          Also ban {authorName}
        </label>
        {alsoBan && (
          <BanLengthSelect
            value={banDays}
            onChange={setBanDays}
            className="w-32"
          />
        )}
      </div>
      {error && <p className="text-sm text-rose-500">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={isBusy}
          className="hover:cursor-pointer"
          onClick={onCancel}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          variant="destructive"
          disabled={isBusy || (isOther && !reasonDetail.trim())}
          className="hover:cursor-pointer"
        >
          {alsoBan ? "Remove and ban" : "Remove comment"}
        </Button>
      </div>
    </form>
  );
}
