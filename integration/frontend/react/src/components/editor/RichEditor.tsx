"use client";

import { AutoFocusPlugin } from "@lexical/react/LexicalAutoFocusPlugin";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import { $getRoot, EditorState, LexicalEditor } from "lexical";
import { Code2, Pilcrow } from "lucide-react";
import React, { useMemo, useRef, useState, type ReactNode } from "react";
import "./style.css";

import { cn } from "@/lib/utils";
import { markdownToPlainText } from "../common/markdownUtils";
import { Separator } from "../ui/separator";
import Theme from "./Theme";
import {
  $convertFromMarkdownString,
  $convertToMarkdownString,
  isRichTextCompatible,
  RICH_EDITOR_NODES,
} from "./markdownSerializer";
import EditorRefPlugin from "./plugins/EditorRefPlugin";
import InitialMarkdownPlugin from "./plugins/InitialMarkdownPlugin";
import ToolbarPlugin from "./plugins/ToolbarPlugin";
import TreeViewPlugin from "./plugins/TreeViewPlugin";

const editorConfig = {
  namespace: "ThreadFS",
  nodes: RICH_EDITOR_NODES,
  onError(error: Error) {
    throw error;
  },
  theme: Theme,
};

export type RichEditorValue = {
  markdown: string;
  text: string;
};

type RichEditorProps = {
  disabled?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
  initialMarkdown?: string | null;
  minHeightClassName?: string;
  /** Whether the formatting and mode buttons, and actions, are showing. */
  showControls?: boolean;
  /** Goes at the end of the row of buttons, such as a submit button. */
  actions?: ReactNode;
  /** More buttons after the mode switch, such as GIFs. */
  tools?: ReactNode;
  /** Between the text and the buttons, such as an attached GIF. */
  attachments?: ReactNode;
  /** Only the actions in the row of buttons, such as while a question there needs the room. */
  actionsOnly?: boolean;
  onChange?: (value: RichEditorValue) => void;
};

const RichEditor = ({
  disabled = false,
  placeholder = "Join the discussion...",
  autoFocus = false,
  initialMarkdown = null,
  showControls = true,
  actions,
  tools,
  attachments,
  actionsOnly = false,
  onChange,
}: RichEditorProps) => {
  const editorRef = useRef<LexicalEditor | null>(null);
  const latestMarkdownRef = useRef(initialMarkdown ?? "");
  // Markdown the rich editor can't show unchanged (e.g. HTML or code blocks) opens in markdown mode, so saving
  // an edit doesn't escape it
  const [startsInRichMode] = useState(() =>
    isRichTextCompatible(initialMarkdown ?? ""),
  );
  const [mode, setMode] = useState<"rich" | "markdown">(
    startsInRichMode ? "rich" : "markdown",
  );
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const [isToolbarVisible, setIsToolbarVisible] = useState(false);
  const [markdownDraft, setMarkdownDraft] = useState(initialMarkdown ?? "");
  const canSwitchToRich = useMemo(
    () => mode === "rich" || isRichTextCompatible(markdownDraft),
    [mode, markdownDraft],
  );

  function handleChange(editorState: EditorState, _editor: LexicalEditor) {
    // In markdown mode the textarea is the source of truth; the hidden rich editor's content is stale
    if (modeRef.current === "markdown") return;

    editorState.read(() => {
      const markdown = $convertToMarkdownString();
      const text = $getRoot().getTextContent().trim();

      latestMarkdownRef.current = markdown;
      onChange?.({
        markdown,
        text,
      });
    });
  }

  function switchToMarkdownMode() {
    setMarkdownDraft(latestMarkdownRef.current);
    setMode("markdown");
  }

  function switchToRichMode() {
    if (!canSwitchToRich) return;

    const editor = editorRef.current;
    if (editor) {
      editor.update(() => {
        $convertFromMarkdownString(markdownDraft);
      });
    }

    latestMarkdownRef.current = markdownDraft;
    onChange?.({
      markdown: markdownDraft,
      text: markdownToPlainText(markdownDraft),
    });
    setMode("rich");
  }

  function handleMarkdownDraftChange(value: string) {
    setMarkdownDraft(value);
    latestMarkdownRef.current = value;
    onChange?.({
      markdown: value,
      text: markdownToPlainText(value),
    });
  }

  const modeSwitch = (
    <button
      type="button"
      disabled={disabled || !canSwitchToRich}
      onClick={mode === "rich" ? switchToMarkdownMode : switchToRichMode}
      aria-label={
        mode === "rich" ? "Switch to markdown" : "Switch to rich text"
      }
      title={
        mode === "rich"
          ? "Switch to markdown"
          : canSwitchToRich
            ? "Switch to rich text"
            : "This uses formatting the rich text editor can't show"
      }
      className="text-muted-foreground hover:bg-primary/20 hover:text-foreground flex h-8 items-center gap-1.5 rounded-lg px-2 text-xs font-medium hover:cursor-pointer disabled:opacity-50 disabled:hover:bg-transparent"
    >
      {mode === "rich" ? (
        <>
          <Code2 className="size-4" />
          <span className="hidden @[26rem]:inline">Switch to Markdown</span>
        </>
      ) : (
        <>
          <Pilcrow className="size-4" />
          <span className="hidden @[20rem]:inline">Switch to rich text</span>
        </>
      )}
    </button>
  );

  return (
    <LexicalComposer initialConfig={editorConfig}>
      <div className="editor-container @container">
        {showControls && mode === "rich" && isToolbarVisible && (
          <>
            {/* The switch stays put while the buttons beside it scroll */}
            <div className="mb-1 flex items-center gap-1">
              <ToolbarPlugin disabled={disabled} />
              <div className="flex shrink-0 items-center">{modeSwitch}</div>
            </div>
            <Separator className="h-px" />
          </>
        )}

        {/* Markdown has no formatting buttons, so its bar is only the way back */}
        {showControls && mode === "markdown" && (
          <>
            <div className="mb-1 flex min-h-8 items-center gap-2">
              <span className="text-muted-foreground px-1 text-xs font-medium">
                Markdown
              </span>
              <div className="ml-auto flex items-center">{modeSwitch}</div>
            </div>
            <Separator className="h-px" />
          </>
        )}

        <div className="editor-inner relative">
          <div className={cn(mode === "markdown" && "hidden")}>
            <RichTextPlugin
              contentEditable={
                <ContentEditable
                  className="break-word max-h-64 min-h-8 w-full overflow-y-auto p-1 text-base text-wrap focus:outline-none"
                  ariaLabel={placeholder}
                  aria-placeholder={placeholder}
                  placeholder={
                    <div className="editor-placeholder text-muted-foreground pointer-events-none absolute top-1 left-1 text-base select-none">
                      {placeholder}
                    </div>
                  }
                />
              }
              ErrorBoundary={LexicalErrorBoundary}
            />
          </div>

          {mode === "markdown" && (
            <textarea
              autoFocus
              disabled={disabled}
              value={markdownDraft}
              onChange={(event) =>
                handleMarkdownDraftChange(event.target.value)
              }
              placeholder={placeholder}
              aria-label={placeholder}
              className="break-word field-sizing-content max-h-64 min-h-8 w-full overflow-y-auto p-1 font-mono text-base text-wrap focus:outline-none"
            />
          )}

          <InitialMarkdownPlugin
            initialMarkdown={startsInRichMode ? initialMarkdown : null}
          />
          <EditorRefPlugin editorRef={editorRef} />
          <HistoryPlugin />
          <OnChangePlugin onChange={handleChange} />
          {autoFocus && mode === "rich" && <AutoFocusPlugin />}
        </div>

        {attachments}

        {showControls && (
          <div className="@container mt-1 flex flex-wrap items-center gap-1">
            {!actionsOnly && tools}

            {/* Formatting, as on Reddit: the buttons open on top, where the switch to markdown is */}
            {mode === "rich" && !actionsOnly && (
              <button
                type="button"
                disabled={disabled}
                onClick={() => setIsToolbarVisible((value) => !value)}
                aria-label={
                  isToolbarVisible ? "Hide formatting" : "Show formatting"
                }
                aria-pressed={isToolbarVisible}
                title={isToolbarVisible ? "Hide formatting" : "Show formatting"}
                className={cn(
                  "text-muted-foreground hover:bg-primary/20 flex size-7 items-center justify-center rounded-full text-[13px] font-semibold hover:cursor-pointer",
                  isToolbarVisible && "bg-primary/20 text-foreground",
                )}
              >
                Aa
              </button>
            )}

            <div className="ml-auto flex items-center gap-1">{actions}</div>
          </div>
        )}
      </div>
      <TreeViewPlugin className="hidden" />
    </LexicalComposer>
  );
};

export default RichEditor;
