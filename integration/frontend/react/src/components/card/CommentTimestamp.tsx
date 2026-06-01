import React from "react";

function CommentTimestamp({ value }: { value: string }) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return (
    <time
      dateTime={date.toISOString()}
      title={formatExactTime(date)}
      className="text-muted-foreground cursor-help text-xs"
    >
      {formatRelativeTime(date)}
    </time>
  );
}

export default CommentTimestamp;

// Helper functions
const RELATIVE_TIME_FORMATTER = new Intl.RelativeTimeFormat("en", {
  numeric: "auto",
});

function formatRelativeTime(date: Date): string {
  const now = Date.now();
  const diffMs = date.getTime() - now;
  const absMs = Math.abs(diffMs);

  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  const week = 7 * day;
  const month = 30 * day;

  if (absMs < minute) {
    return "just now";
  }

  if (absMs < hour) {
    return RELATIVE_TIME_FORMATTER.format(
      Math.round(diffMs / minute),
      "minute",
    );
  }

  if (absMs < day) {
    return RELATIVE_TIME_FORMATTER.format(Math.round(diffMs / hour), "hour");
  }

  if (absMs < week) {
    return RELATIVE_TIME_FORMATTER.format(Math.round(diffMs / day), "day");
  }

  if (absMs < month) {
    return RELATIVE_TIME_FORMATTER.format(Math.round(diffMs / week), "week");
  }

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatExactTime(date: Date): string {
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
}
