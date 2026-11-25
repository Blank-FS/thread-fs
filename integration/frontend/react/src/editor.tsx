// @threadfs/react/editor: the comment box's rich markdown editor on its own (formatting toolbar, markdown mode, the
// cheatsheet), for a host's other writing, so it's written like comments without loading the widget. It writes the
// markdown ThreadFSMarkdown renders. No stylesheet here: the host imports "@threadfs/react/styles.css" as for the
// widget, and the root class below brings its rules into scope.
import { useState, type ReactNode } from "react";
import LengthCounter from "./components/editor/LengthCounter";
import RichEditor, {
  type RichEditorValue,
} from "./components/editor/RichEditor";
import { countCharacters } from "./lib/commentLength";
import { cn } from "./lib/utils";

/** The text as markdown, and as plain text (for counting, or checking it isn't empty). */
export type ThreadFSEditorValue = RichEditorValue;

export type ThreadFSEditorProps = {
  /** Text to start from, such as when editing. */
  initialMarkdown?: string | null;
  placeholder?: string;
  autoFocus?: boolean;
  disabled?: boolean;
  /** Counts the markdown's characters as they near this, and says when there are too many. What's too long can still be
   * written, so the host refuses it (Array.from(value.markdown).length, an emoji being one). */
  maxLength?: number;
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
  maxLength,
  actions,
  onChange,
  className,
}: ThreadFSEditorProps) {
  const [length, setLength] = useState(() =>
    countCharacters(initialMarkdown ?? ""),
  );

  return (
    <div className={cn("threadfs-root", className)}>
      <RichEditor
        initialMarkdown={initialMarkdown}
        placeholder={placeholder}
        autoFocus={autoFocus}
        disabled={disabled}
        actions={actions}
        attachments={
          maxLength !== undefined && (
            <LengthCounter length={length} max={maxLength} />
          )
        }
        onChange={(value) => {
          if (maxLength !== undefined)
            setLength(countCharacters(value.markdown));
          onChange?.(value);
        }}
      />
    </div>
  );
}
