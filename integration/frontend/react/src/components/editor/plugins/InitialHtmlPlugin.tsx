import React from "react";
import { $generateNodesFromDOM } from "@lexical/html";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { $getRoot, $insertNodes } from "lexical";

function InitialHtmlPlugin({ initialHtml }: { initialHtml?: string | null }) {
  const [editor] = useLexicalComposerContext();
  const didInitializeRef = React.useRef(false);

  React.useEffect(() => {
    if (didInitializeRef.current) return;
    didInitializeRef.current = true;

    if (!initialHtml?.trim()) return;

    editor.update(() => {
      const parser = new DOMParser();
      const dom = parser.parseFromString(initialHtml, "text/html");
      const nodes = $generateNodesFromDOM(editor, dom);

      const root = $getRoot();
      root.clear();
      root.select();

      $insertNodes(nodes);
    });
  }, [editor, initialHtml]);

  return null;
}

export default InitialHtmlPlugin;
