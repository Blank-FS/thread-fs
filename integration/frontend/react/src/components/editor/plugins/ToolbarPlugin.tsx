// TODO - Add link, quote, and spoiler buttons

import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
  $createListNode,
  $insertList,
  $isListItemNode,
  $isListNode,
  $removeList,
  INSERT_ORDERED_LIST_COMMAND,
  INSERT_UNORDERED_LIST_COMMAND,
  ListNode,
  REMOVE_LIST_COMMAND,
} from "@lexical/list";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { $createHeadingNode, $createQuoteNode } from "@lexical/rich-text";
import { $setBlocksType } from "@lexical/selection";
import { mergeRegister } from "@lexical/utils";
import {
  $create,
  $createParagraphNode,
  $getSelection,
  $isRangeSelection,
  CAN_REDO_COMMAND,
  CAN_UNDO_COMMAND,
  COMMAND_PRIORITY_CRITICAL,
  COMMAND_PRIORITY_EDITOR,
  COMMAND_PRIORITY_HIGH,
  COMMAND_PRIORITY_LOW,
  ElementNode,
  FORMAT_ELEMENT_COMMAND,
  FORMAT_TEXT_COMMAND,
  KEY_BACKSPACE_COMMAND,
  KEY_ENTER_COMMAND,
  REDO_COMMAND,
  SELECTION_CHANGE_COMMAND,
  UNDO_COMMAND,
} from "lexical";
import {
  Bold,
  EyeOff,
  Heading,
  Italic,
  List,
  ListOrdered,
  Quote,
  Strikethrough,
  Underline,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";

const ToolbarPlugin = ({ disabled = false }: { disabled?: boolean }) => {
  const [editor] = useLexicalComposerContext();
  const toolbarRef = useRef(null);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [isBold, setIsBold] = useState(false);
  const [isItalic, setIsItalic] = useState(false);
  const [isUnderline, setIsUnderline] = useState(false);
  const [isStrikethrough, setIsStrikethrough] = useState(false);
  const [isSpoiler, setIsSpoiler] = useState(false);
  const [isHeading, setIsHeading] = useState(false);
  const [isQuote, setIsQuote] = useState(false);
  const [isBulletList, setIsBulletList] = useState(false);
  const [isNumberList, setIsNumberList] = useState(false);

  const $updateToolbar = useCallback(() => {
    const selection = $getSelection();
    if ($isRangeSelection(selection)) {
      // Update Heading
      setIsHeading(
        selection.getNodes().some((node) => {
          return node.getParent()?.getType() === "heading";
        }),
      );

      setIsQuote(
        selection.getNodes().some((node) => {
          return (
            node.getType() === "quote" || node.getParent()?.getType() === "quote"
          );
        }),
      );

      // Update List Types
      let bulletListFound = false;
      let numberListFound = false;

      selection.getNodes().some((node) => {
        if (node.getParent()) {
          const parent = node.getParent() as ListNode;
          const parentType = node.getParent()?.getType();
          if (parentType === "list") {
            const listType = parent.getListType();
            if (listType === "bullet") {
              bulletListFound = true;
            } else if (listType === "number") {
              numberListFound = true;
            }
          } else if (parentType === "listitem") {
            const grandParent = parent.getParent() as ListNode;
            const grandParentType = grandParent.getType();
            if (grandParentType === "list") {
              const listType = grandParent.getListType();
              if (listType === "bullet") {
                bulletListFound = true;
              } else if (listType === "number") {
                numberListFound = true;
              }
            }
          } else if (node.getType() === "list") {
            const listType = (node as ListNode).getListType();
            console.log("listType:", listType);
            if (listType === "bullet") {
              bulletListFound = true;
            } else if (listType === "number") {
              numberListFound = true;
            }
          }
        }
      });

      setIsBulletList(bulletListFound);
      setIsNumberList(numberListFound);

      // Update text format
      setIsBold(selection.hasFormat("bold"));
      setIsItalic(selection.hasFormat("italic"));
      setIsUnderline(selection.hasFormat("underline"));
      setIsStrikethrough(selection.hasFormat("strikethrough"));
      setIsSpoiler(selection.hasFormat("highlight"));
    }
  }, []);

  useEffect(() => {
    return mergeRegister(
      editor.registerUpdateListener(({ editorState }) => {
        editorState.read(
          () => {
            $updateToolbar();
          },
          { editor },
        );
      }),
      editor.registerCommand(
        SELECTION_CHANGE_COMMAND,
        (_payload, _newEditor) => {
          $updateToolbar();
          return false;
        },
        COMMAND_PRIORITY_LOW,
      ),
      editor.registerCommand(
        CAN_UNDO_COMMAND,
        (payload) => {
          setCanUndo(payload);
          return false;
        },
        COMMAND_PRIORITY_LOW,
      ),
      editor.registerCommand(
        CAN_REDO_COMMAND,
        (payload) => {
          setCanRedo(payload);
          return false;
        },
        COMMAND_PRIORITY_LOW,
      ),
      editor.registerCommand(
        INSERT_UNORDERED_LIST_COMMAND,
        () => {
          $insertList("bullet");
          return true;
        },
        COMMAND_PRIORITY_LOW,
      ),
      editor.registerCommand(
        INSERT_ORDERED_LIST_COMMAND,
        () => {
          $insertList("number");
          return true;
        },
        COMMAND_PRIORITY_LOW,
      ),
      editor.registerCommand(
        REMOVE_LIST_COMMAND,
        () => {
          const selection = $getSelection();
          if (!$isRangeSelection(selection)) return false;

          const anchor = selection.anchor.getNode();
          if ($isListItemNode(anchor)) {
            const paragraph = $createParagraphNode();
            anchor.replace(paragraph);
            paragraph.select();
            return true;
          }

          const anchorParent = anchor.getParent();
          if ($isListItemNode(anchorParent)) {
            const paragraph = $createParagraphNode();
            anchorParent.replace(paragraph);
            paragraph.select();
            return true;
          }

          return false;
        },
        COMMAND_PRIORITY_LOW,
      ),
      editor.registerCommand(
        KEY_ENTER_COMMAND,
        (event) => {
          const selection = $getSelection();
          if (!$isRangeSelection(selection) || !selection.isCollapsed())
            return false;

          // Start from whatever node the caret is in
          let node = selection.anchor.getNode();

          // Walk up to the nearest ListItemNode
          let listItem = node;
          while (listItem && !$isListItemNode(listItem))
            listItem = listItem.getParent() as ElementNode;
          if (!listItem || !$isListItemNode(listItem)) return false;

          // Only handle the "empty list item" case
          if (listItem.getTextContent().length !== 0) return false;

          const list = listItem.getParent();
          if (!list || !$isListNode(list)) return false;

          // Create a paragraph AFTER the list (outside the list)
          const paragraph = $createParagraphNode();
          list.insertAfter(paragraph);

          event?.preventDefault();
          // Remove the empty list item
          listItem.remove();

          // If the list is now empty, remove the list too
          if (list.getChildrenSize() === 0) {
            list.remove();
          }

          // Put caret into the paragraph
          paragraph.select();

          return true;
        },
        COMMAND_PRIORITY_CRITICAL,
      ),
    );
  }, [editor, $updateToolbar]);

  return (
    <div className="toolbar mb-1 flex items-center gap-1" ref={toolbarRef}>
      {/* Bold Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.dispatchCommand(FORMAT_TEXT_COMMAND, "bold");
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isBold &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Bold"
          >
            <Bold className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Bold</p>
        </TooltipContent>
      </Tooltip>

      {/* Italic Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.dispatchCommand(FORMAT_TEXT_COMMAND, "italic");
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isItalic &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Italics"
          >
            <Italic className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Italic</p>
        </TooltipContent>
      </Tooltip>

      {/* Underline Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.dispatchCommand(FORMAT_TEXT_COMMAND, "underline");
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isUnderline &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Underline"
          >
            <Underline className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Underline</p>
        </TooltipContent>
      </Tooltip>

      {/* Strikethrough Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.dispatchCommand(FORMAT_TEXT_COMMAND, "strikethrough");
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isStrikethrough &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Strikethrough"
          >
            <Strikethrough className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Strikethrough</p>
        </TooltipContent>
      </Tooltip>

      {/* Spoiler Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.dispatchCommand(FORMAT_TEXT_COMMAND, "highlight");
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isSpoiler &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Spoiler"
          >
            <EyeOff className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Spoiler</p>
        </TooltipContent>
      </Tooltip>

      {/* Quote Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.update(() => {
                const selection = $getSelection();
                if (!$isRangeSelection(selection)) return;

                if (isQuote) {
                  $setBlocksType(selection, () => $createParagraphNode());
                } else {
                  $setBlocksType(selection, () => $createQuoteNode());
                }
              });
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isQuote &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Quote"
          >
            <Quote className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Quote</p>
        </TooltipContent>
      </Tooltip>

      {/* Heading Button */}
      {/* <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.update(() => {
                const selection = $getSelection();
                if ($isRangeSelection(selection)) {
                  if (isHeading) {
                    $setBlocksType(selection, () => $createParagraphNode());
                    $updateToolbar();
                    return;
                  }
                  $setBlocksType(selection, () => $createHeadingNode("h1"));
                  $updateToolbar();
                }
              });
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isHeading &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Heading"
          >
            <Heading className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Heading</p>
        </TooltipContent>
      </Tooltip> */}

      <Separator orientation="vertical" className="min-h-6 w-px" />

      {/* Bullet List Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.dispatchCommand(
                isBulletList
                  ? REMOVE_LIST_COMMAND
                  : INSERT_UNORDERED_LIST_COMMAND,
                undefined,
              );
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isBulletList &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Bullet List"
          >
            <List className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Bullet List</p>
        </TooltipContent>
      </Tooltip>

      {/* Number List Button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              editor.dispatchCommand(
                isNumberList
                  ? REMOVE_LIST_COMMAND
                  : INSERT_ORDERED_LIST_COMMAND,
                undefined,
              );
            }}
            className={cn(
              "hover:bg-primary/20 flex size-8 items-center justify-center rounded-lg",
              isNumberList &&
                "active bg-primary text-primary-foreground hover:bg-primary",
            )}
            aria-label="Format Number List"
          >
            <ListOrdered className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-semibold">Number List</p>
        </TooltipContent>
      </Tooltip>
    </div>
  );
};

export default ToolbarPlugin;
