import { useRef } from "react";

/**
 * A ref that always holds the latest value. For callbacks a host passes in, such as getAuthToken: sites pass them
 * inline, so every re-render brings a new function that does the same thing. Depending on the function itself would
 * reload everything each time (a whole comment section, whenever the host page re-renders); reading it from here
 * calls the newest one without counting it as a change.
 */
export function useLatest<T>(value: T) {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}
