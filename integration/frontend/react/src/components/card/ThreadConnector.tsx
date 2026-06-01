import {
  ConnectorGeometry,
  ConnectorPoint,
  ThreadFSComment,
} from "@/lib/types";
import React, {
  RefObject,
  useCallback,
  useLayoutEffect,
  useState,
} from "react";

type ThreadConnectorProps = {
  containerRef: RefObject<HTMLElement | null>;
  parentAvatarRef: RefObject<HTMLImageElement | null>;
  repliesButtonRef: RefObject<HTMLButtonElement | null>;
  replyAvatarRefs: RefObject<Map<string, HTMLImageElement>>;
  replies: ThreadFSComment[];
  hasReplies: boolean;
  areRepliesExpanded: boolean;
  measureVersion: number;
};

function ThreadConnector({
  containerRef,
  parentAvatarRef,
  repliesButtonRef,
  replyAvatarRefs,
  replies,
  hasReplies,
  areRepliesExpanded,
  measureVersion,
}: ThreadConnectorProps) {
  const [geometry, setGeometry] = useState<ConnectorGeometry | null>(null);

  const handleGeometryChange = useCallback((next: ConnectorGeometry | null) => {
    setGeometry((prev) =>
      areConnectorGeometriesEqual(prev, next) ? prev : next,
    );
  }, []);

  useMeasuredConnectorGeometry({
    containerRef,
    parentAvatarRef,
    repliesButtonRef,
    replyAvatarRefs,
    replies,
    hasReplies,
    areRepliesExpanded,
    measureVersion,
    onChange: handleGeometryChange,
  });

  if (!hasReplies || !geometry) return null;

  const { width, height, railX, startY, buttonPoint, replyPoints } = geometry;

  const branchLength = 32;
  const radius = 12;
  const branchEndX = railX + branchLength;

  const branchPoints = [
    ...(buttonPoint ? [buttonPoint] : []),
    ...(areRepliesExpanded ? replyPoints : []),
  ].sort((a, b) => a.y - b.y);

  if (branchPoints.length === 0) return null;

  const lastBranch = branchPoints[branchPoints.length - 1];
  const railEndY = Math.max(startY, lastBranch.y - radius);

  const path = [
    `M ${railX} ${startY}`,
    `V ${railEndY}`,
    ...branchPoints.flatMap((point) => [
      `M ${railX} ${point.y - radius}`,
      `Q ${railX} ${point.y} ${railX + radius} ${point.y}`,
      `H ${branchEndX}`,
    ]),
  ].join(" ");

  return (
    <svg
      aria-hidden="true"
      className="text-border pointer-events-none absolute top-0 left-0 z-0 overflow-visible"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
    >
      <path
        d={path}
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default ThreadConnector;

// Helper functions
function useMeasuredConnectorGeometry({
  containerRef,
  parentAvatarRef,
  repliesButtonRef,
  replyAvatarRefs,
  replies,
  hasReplies,
  areRepliesExpanded,
  measureVersion,
  onChange,
}: {
  containerRef: RefObject<HTMLElement | null>;
  parentAvatarRef: RefObject<HTMLImageElement | null>;
  repliesButtonRef: RefObject<HTMLButtonElement | null>;
  replyAvatarRefs: RefObject<Map<string, HTMLImageElement>>;
  replies: ThreadFSComment[];
  hasReplies: boolean;
  areRepliesExpanded: boolean;
  measureVersion: number;
  onChange: (geometry: ConnectorGeometry | null) => void;
}) {
  useLayoutEffect(() => {
    if (!hasReplies) {
      onChange(null);
      return;
    }

    const container = containerRef.current;
    const parentAvatar = parentAvatarRef.current;
    const repliesButton = repliesButtonRef.current;

    if (!container || !parentAvatar || !repliesButton) {
      onChange(null);
      return;
    }

    let frame = 0;
    let secondFrame = 0;

    const measure = () => {
      const containerRect = container.getBoundingClientRect();
      const parentAvatarRect = parentAvatar.getBoundingClientRect();
      const repliesButtonRect = repliesButton.getBoundingClientRect();

      const railX =
        parentAvatarRect.left - containerRect.left + parentAvatarRect.width / 2;

      const startY = parentAvatarRect.bottom - containerRect.top;

      const buttonPoint = {
        x: repliesButtonRect.left - containerRect.left,
        y:
          repliesButtonRect.top -
          containerRect.top +
          repliesButtonRect.height / 2,
      };

      const replyPoints =
        areRepliesExpanded && replies.length > 0
          ? replies
              .map((reply) => {
                const node = replyAvatarRefs.current.get(reply.id);
                if (!node) return null;

                const rect = node.getBoundingClientRect();

                return {
                  x: rect.left - containerRect.left + rect.width / 2,
                  y: rect.top - containerRect.top + rect.height / 2,
                };
              })
              .filter((point): point is ConnectorPoint => point != null)
          : [];

      const endY = Math.max(
        startY,
        buttonPoint.y,
        ...replyPoints.map((point) => point.y),
      );

      onChange({
        width: containerRect.width,
        height: containerRect.height,
        railX,
        startY,
        endY,
        buttonPoint,
        replyPoints,
      });
    };

    const scheduleMeasure = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(measure);
    };

    scheduleMeasure();

    secondFrame = window.requestAnimationFrame(scheduleMeasure);

    const observer = new ResizeObserver(scheduleMeasure);
    observer.observe(container);
    observer.observe(parentAvatar);
    observer.observe(repliesButton);

    for (const node of replyAvatarRefs.current.values()) {
      observer.observe(node);
    }

    window.addEventListener("resize", scheduleMeasure);

    return () => {
      window.cancelAnimationFrame(frame);
      window.cancelAnimationFrame(secondFrame);
      observer.disconnect();
      window.removeEventListener("resize", scheduleMeasure);
    };
  }, [
    containerRef,
    parentAvatarRef,
    repliesButtonRef,
    replyAvatarRefs,
    replies,
    hasReplies,
    areRepliesExpanded,
    measureVersion,
    onChange,
  ]);
}

function areConnectorPointsEqual(
  a: ConnectorPoint | null,
  b: ConnectorPoint | null,
): boolean {
  if (a === b) return true;
  if (!a || !b) return false;

  return (
    Math.round(a.x) === Math.round(b.x) && Math.round(a.y) === Math.round(b.y)
  );
}

function areConnectorGeometriesEqual(
  a: ConnectorGeometry | null,
  b: ConnectorGeometry | null,
): boolean {
  if (a === b) return true;
  if (!a || !b) return false;

  if (
    Math.round(a.width) !== Math.round(b.width) ||
    Math.round(a.height) !== Math.round(b.height) ||
    Math.round(a.railX) !== Math.round(b.railX) ||
    Math.round(a.startY) !== Math.round(b.startY) ||
    Math.round(a.endY) !== Math.round(b.endY)
  ) {
    return false;
  }

  if (!areConnectorPointsEqual(a.buttonPoint, b.buttonPoint)) {
    return false;
  }

  if (a.replyPoints.length !== b.replyPoints.length) {
    return false;
  }

  return a.replyPoints.every((point, index) =>
    areConnectorPointsEqual(point, b.replyPoints[index]),
  );
}
