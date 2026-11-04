import { RefreshCw } from "lucide-react";
import { Button } from "../ui/button";
import type { PagedList } from "./shared";

/** The right end of a list's toolbar: how many there are, and a refresh. */
export function ListStatus({
  list,
  label,
}: {
  list: PagedList<unknown>;
  label: string;
}) {
  return (
    <div className="ml-auto flex items-center gap-1">
      {!list.isLoading && list.total != null && (
        <span className="text-muted-foreground text-sm whitespace-nowrap">
          {list.total} {label}
        </span>
      )}
      <Button
        type="button"
        size="icon-sm"
        variant="ghost"
        aria-label="Refresh"
        title="Refresh"
        className="hover:cursor-pointer"
        onClick={list.reload}
      >
        <RefreshCw />
      </Button>
    </div>
  );
}
