// The widget's click guard alone, for a host's own controls in a page other sites can frame
export {
  ClickGuardProvider,
  useClickGuard,
  useGuardedControls,
} from "./lib/clickGuard";
export type { ConfirmClick, ThreadFSClickAction } from "./lib/clickGuard";
