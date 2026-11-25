import { createContext, useContext } from "react";

/** Core's own limit, until the community's config says (an older core doesn't). */
export const DEFAULT_MAX_COMMENT_LENGTH = 10_000;

// How many characters of markdown a comment can have, for every comment box in the widget
export const MaxCommentLengthContext = createContext(
  DEFAULT_MAX_COMMENT_LENGTH,
);

export const useMaxCommentLength = () => useContext(MaxCommentLengthContext);

/** Characters as core counts them: an emoji is one. */
export const countCharacters = (text: string) => Array.from(text).length;
