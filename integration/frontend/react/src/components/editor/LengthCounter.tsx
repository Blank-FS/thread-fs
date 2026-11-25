import { cn } from "@/lib/utils";

// Shown from here, so most writing never sees it
const NEAR = 0.9;

/** "9,412 / 10,000" as text nears its limit, and that it's too long past it. */
function LengthCounter({ length, max }: { length: number; max: number }) {
  if (length < max * NEAR) return null;
  const isTooLong = length > max;

  return (
    <p
      role={isTooLong ? "status" : undefined}
      className={cn(
        "px-1 pt-1 text-xs tabular-nums",
        isTooLong ? "text-destructive" : "text-muted-foreground",
      )}
    >
      {length.toLocaleString("en-US")} / {max.toLocaleString("en-US")}
      {isTooLong && " · too long"}
    </p>
  );
}

export default LengthCounter;
