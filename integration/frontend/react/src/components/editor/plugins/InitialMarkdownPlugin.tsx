import React from "react";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { $convertFromMarkdownString } from "../markdownSerializer";

function InitialMarkdownPlugin({
  initialMarkdown,
}: {
  initialMarkdown?: string | null;
}) {
  const [editor] = useLexicalComposerContext();
  const didInitializeRef = React.useRef(false);

  React.useEffect(() => {
    if (didInitializeRef.current) return;
    didInitializeRef.current = true;

    if (!initialMarkdown?.trim()) return;

    editor.update(() => {
      $convertFromMarkdownString(initialMarkdown);
    });
  }, [editor, initialMarkdown]);

  return null;
}

export default InitialMarkdownPlugin;
