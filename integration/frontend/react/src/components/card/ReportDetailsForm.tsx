import { useState, type FormEvent } from "react";
import { brandButtonClass } from "../moderation/shared";
import { Button } from "../ui/button";

const MAX_DETAILS = 100;

/** The description a report gives when none of the community's reasons fit. */
export default function ReportDetailsForm({
  onReport,
  onCancel,
}: {
  onReport: (details: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [details, setDetails] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const description = details.trim();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    try {
      setIsBusy(true);
      await onReport(description);
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <form
      className="bg-muted/50 mt-3 space-y-3 rounded-lg p-3"
      onSubmit={(event) => void handleSubmit(event)}
    >
      <textarea
        value={details}
        onChange={(event) => setDetails(event.target.value)}
        aria-label="What's wrong with this comment?"
        placeholder="What's wrong with this comment?"
        maxLength={MAX_DETAILS}
        rows={3}
        className="border-input placeholder:text-muted-foreground focus-visible:border-ring w-full resize-y rounded-lg border bg-transparent px-2.5 py-1.5 text-sm outline-none"
      />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className="text-muted-foreground mr-auto text-xs">
          {details.length}/{MAX_DETAILS}
        </span>
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
          disabled={isBusy || !description}
          className={brandButtonClass}
        >
          Send report
        </Button>
      </div>
    </form>
  );
}
