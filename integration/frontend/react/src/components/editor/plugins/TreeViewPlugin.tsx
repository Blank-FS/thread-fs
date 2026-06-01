import React from "react";
import type { JSX } from "react";

import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { TreeView } from "@lexical/react/LexicalTreeView";
import { cn } from "@/lib/utils";

const TreeViewPlugin = ({ className }: { className?: string }) => {
  const [editor] = useLexicalComposerContext();
  return (
    <TreeView
      viewClassName={cn("tree-view-output", className)}
      treeTypeButtonClassName="debug-treetype-button"
      timeTravelPanelClassName="debug-timetravel-panel"
      timeTravelButtonClassName="debug-timetravel-button"
      timeTravelPanelSliderClassName="debug-timetravel-panel-slider"
      timeTravelPanelButtonClassName="debug-timetravel-panel-button"
      editor={editor}
    />
  );
};

export default TreeViewPlugin;
