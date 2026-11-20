// @threadfs/react/editor: the comment box's rich markdown editor on its own (formatting toolbar, markdown mode, the
// cheatsheet), for a host's other writing, so it's written like comments without loading the widget. It writes the
// markdown ThreadFSMarkdown renders. No stylesheet here: the host imports "@threadfs/react/styles.css" as for the
// widget, and the root class below brings its rules into scope.
import type { ReactNode } from "react";
import RichEditor, { type RichEditorValue } from "./components/editor/RichEditor";
import { cn } from "./lib/utils";

/** The text as markdown, and as plain text (for counting, or checking it isn't empty). */
export type ThreadFSEditorValue = RichEditorValue;

export type ThreadFSEditorProps = {
  /** Text to start from, such as when editing. */
  initialMarkdown?: string | null;
  placeholder?: string;
  autoFocus?: boolean;
  disabled?: boolean;
  /** At the end of the row of buttons, such as a submit button. */
  actions?: ReactNode;
  onChange?: (value: ThreadFSEditorValue) => void;
  className?: string;
};

export function ThreadFSEditor({
  initialMarkdown = null,
  placeholder,
  autoFocus = false,
  disabled = false,
  actions,
  onChange,
  className,
}: ThreadFSEditorProps) {
  return (
    <div className={cn("threadfs-root", className)}>
      <RichEditor
        initialMarkdown={initialMarkdown}
        placeholder={placeholder}
        autoFocus={autoFocus}
        disabled={disabled}
        actions={actions}
        onChange={onChange}
      />
    </div>
  );
}
