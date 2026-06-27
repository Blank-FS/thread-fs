"use client";

import { LinkNode } from "@lexical/link";
import { ListItemNode, ListNode } from "@lexical/list";
import { AutoFocusPlugin } from "@lexical/react/LexicalAutoFocusPlugin";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import { HeadingNode, QuoteNode } from "@lexical/rich-text";
import {
  $getRoot,
  EditorState,
  LexicalEditor,
  ParagraphNode,
  TextNode,
} from "lexical";
import React from "react";
import "./style.css";

import { Separator } from "../ui/separator";
import Theme from "./Theme";
import { $convertToMarkdownString } from "./markdownSerializer";
import InitialMarkdownPlugin from "./plugins/InitialMarkdownPlugin";
import ToolbarPlugin from "./plugins/ToolbarPlugin";
import TreeViewPlugin from "./plugins/TreeViewPlugin";

const editorConfig = {
  namespace: "ThreadFS",
  nodes: [
    ParagraphNode,
    TextNode,
    HeadingNode,
    QuoteNode,
    ListItemNode,
    ListNode,
    LinkNode,
  ],
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
  onChange?: (value: RichEditorValue) => void;
};

const RichEditor = ({
  disabled = false,
  placeholder = "Join the discussion...",
  autoFocus = false,
  initialMarkdown = null,
  onChange,
}: RichEditorProps) => {
  function handleChange(editorState: EditorState, _editor: LexicalEditor) {
    editorState.read(() => {
      const markdown = $convertToMarkdownString();
      const text = $getRoot().getTextContent().trim();

      onChange?.({
        markdown,
        text,
      });
    });
  }

  return (
    <LexicalComposer initialConfig={editorConfig}>
      <div className="editor-container">
        <ToolbarPlugin disabled={disabled} />
        <Separator className="mb-1" />
        <div className="editor-inner relative">
          <RichTextPlugin
            contentEditable={
              <ContentEditable
                className="editor-input break-word max-h-[72vh] min-h-24 overflow-y-auto rounded-lg p-1 text-sm text-wrap focus:outline-none"
                aria-placeholder={placeholder}
                placeholder={
                  <div className="editor-placeholder text-muted-foreground absolute top-1 left-1 text-sm">
                    {placeholder}
                  </div>
                }
              />
            }
            ErrorBoundary={LexicalErrorBoundary}
          />

          <InitialMarkdownPlugin initialMarkdown={initialMarkdown} />
          <HistoryPlugin />
          <OnChangePlugin onChange={handleChange} />
          {autoFocus && <AutoFocusPlugin />}
        </div>
      </div>
      <TreeViewPlugin className="hidden" />
    </LexicalComposer>
  );
};

export default RichEditor;
