import { useEffect } from "react";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { LexicalEditor } from "lexical";

function EditorRefPlugin({
  editorRef,
}: {
  editorRef: React.MutableRefObject<LexicalEditor | null>;
}) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    editorRef.current = editor;
    return () => {
      editorRef.current = null;
    };
  }, [editor, editorRef]);

  return null;
}

export default EditorRefPlugin;
