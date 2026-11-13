import {
  Ban,
  Flag,
  ListChecks,
  MessagesSquare,
  Settings,
  ShieldOff,
  Trash2,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getEmbedConfig, getEmbedMe } from "../lib/api";
import { ThreadFSApiError } from "../lib/errors";
import { listReasons, listReports } from "../lib/moderationApi";
import type {
  EmbedMe,
  ModerationComment,
  ThreadFSCommentUser,
  ThreadFSReason,
  ThreadFSRequestContext,
  ThreadFSThread,
} from "../lib/types";
import { ImageHostsContext } from "../lib/imageHosts";
import { useLatest } from "../lib/useLatest";
import { cn } from "../lib/utils";
import { AdminPanel } from "./moderation/AdminPanel";
import {
  BansPanel,
  LogPanel,
  UserPanel,
  UsersPanel,
} from "./moderation/PeoplePanels";
import {
  CommentsPanel,
  RemovedPanel,
  ReportsPanel,
} from "./moderation/QueuePanels";
import {
  EmptyNote,
  ErrorNote,
  ListSkeleton,
  ModerationProvider,
  type ModerationRequest,
} from "./moderation/shared";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { TooltipProvider } from "./ui/tooltip";

export type ThreadFSModerationProps = {
  apiBaseUrl: string;
  communityKey: string;

  /** A token whose host-signed threadfs_role claim makes the viewer staff. */
  authToken?: string | null;
  getAuthToken?: () => Promise<string | null>;

  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;
  /** The page showing a comment's thread; links to one comment get #c-<id> added. Defaults to its source_url. */
  threadUrl?: (comment: Pick<ModerationComment, "thread">) => string | null;

  title?: string;
  className?: string;
  pageSize?: number;
};

const TABS = [
  { value: "reports", label: "Reports", icon: Flag },
  { value: "removed", label: "Removed", icon: Trash2 },
  { value: "comments", label: "Comments", icon: MessagesSquare },
  { value: "users", label: "Users", icon: Users },
  { value: "bans", label: "Bans", icon: Ban },
  { value: "log", label: "Log", icon: ListChecks },
];

export function ThreadFSModeration({
  apiBaseUrl,
  communityKey,
  authToken,
  getAuthToken,
  authorProfileUrl,
  threadUrl,
  title = "Moderation",
  className,
  pageSize = 20,
}: ThreadFSModerationProps) {
  const [me, setMe] = useState<EmbedMe | null>(null);
  const [reasons, setReasons] = useState<ThreadFSReason[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("reports");
  const [userFilter, setUserFilter] = useState<ThreadFSCommentUser | null>(
    null,
  );
  const [threadFilter, setThreadFilter] = useState<ThreadFSThread | null>(null);
  const [logTarget, setLogTarget] = useState<ThreadFSCommentUser | null>(null);
  const [openedUser, setOpenedUser] = useState<ThreadFSCommentUser | null>(
    null,
  );
  const [version, setVersion] = useState(0);
  const [openReports, setOpenReports] = useState<number | null>(null);
  const token = useRef<string | null>(authToken ?? null);

  // The community's image hosts, from its config (lib/imageHosts.ts); none, so every image a link, until it loads
  const [imageHosts, setImageHosts] = useState<string[]>([]);
  useEffect(() => {
    let isCurrent = true;
    getEmbedConfig({ apiBaseUrl, communityKey, authToken: null })
      .then((config) => {
        if (isCurrent) setImageHosts(config.image_hosts ?? []);
      })
      .catch(() => {});
    return () => {
      isCurrent = false;
    };
  }, [apiBaseUrl, communityKey]);

  const context = useCallback(
    (): ThreadFSRequestContext => ({
      apiBaseUrl,
      communityKey,
      authToken: token.current,
    }),
    [apiBaseUrl, communityKey],
  );

  // The host's latest getAuthToken, without a new copy of it reloading the panel (lib/useLatest.ts)
  const getAuthTokenRef = useLatest(getAuthToken);
  const refreshToken = useCallback(async () => {
    const getToken = getAuthTokenRef.current;
    token.current = getToken ? await getToken() : (authToken ?? null);
    return token.current;
  }, [authToken, getAuthTokenRef]);

  // Moderators leave this page open for longer than a token lasts
  const request = useCallback<ModerationRequest>(
    async (action) => {
      try {
        return await action(context());
      } catch (err) {
        if (!(err instanceof ThreadFSApiError) || err.status !== 401) {
          throw err;
        }

        if (!(await refreshToken())) throw err;
        return action(context());
      }
    },
    [context, refreshToken],
  );

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError(null);

      try {
        await refreshToken();
        const resolvedMe = token.current ? await getEmbedMe(context()) : null;
        const [resolvedReasons, reports] = resolvedMe?.staff_role
          ? await Promise.all([
              listReasons(context()),
              listReports(context(), { limit: 1, offset: 0 }),
            ])
          : [[], null];

        if (isMounted) {
          setMe(resolvedMe);
          setReasons(resolvedReasons);
          setOpenReports(reports?.total ?? null);
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(
            err instanceof Error ? err.message : "Failed to load moderation",
          );
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void bootstrap();

    return () => {
      isMounted = false;
    };
  }, [context, refreshToken]);

  const syncOpenReports = useCallback(() => {
    request((ctx) => listReports(ctx, { limit: 1, offset: 0 }))
      .then((page) => setOpenReports(page.total))
      .catch(() => {}); // only a badge: the queue itself shows any real error
  }, [request]);

  const shared = useMemo(
    () => ({
      request,
      reasons,
      pageSize,
      authorProfileUrl,
      threadUrl,
      version,
      refresh: () => setVersion((value) => value + 1),
      onOpenReports: setOpenReports,
      syncOpenReports,
      setReasons,
      me,
      openUser: setOpenedUser,
      showUserComments(user: ThreadFSCommentUser) {
        setUserFilter(user);
        setOpenedUser(null);
        setTab("comments");
      },
      showUserLog(user: ThreadFSCommentUser) {
        setLogTarget(user);
        setOpenedUser(null);
        setTab("log");
      },
      showThreadComments(thread: ThreadFSThread) {
        setThreadFilter(thread);
        setTab("comments");
      },
    }),
    [
      request,
      reasons,
      pageSize,
      authorProfileUrl,
      threadUrl,
      version,
      syncOpenReports,
      me,
    ],
  );

  const view = (
    <TooltipProvider>
      <section
        className={cn(
          "threadfs-root @container mx-auto w-full space-y-4",
          className,
        )}
        data-threadfs-community-key={communityKey}
      >
        {(title || me?.staff_role) && (
          <div className="flex items-center justify-between gap-2">
            {title && (
              <h2 className="border-tfs-brand-strong dark:border-tfs-brand border-l-4 pl-4 text-lg font-bold sm:text-xl">
                {title}
              </h2>
            )}
            <div className="ml-auto flex items-center gap-1">
              {me?.staff_role && (
                <Badge variant="outline" className="capitalize">
                  {me.staff_role}
                </Badge>
              )}
              {me?.staff_role === "admin" && (
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  aria-label="Admin"
                  title="Admin"
                  aria-pressed={tab === "settings"}
                  className="hover:cursor-pointer"
                  onClick={() => setTab("settings")}
                >
                  <Settings />
                </Button>
              )}
            </div>
          </div>
        )}

        {isLoading ? (
          <ListSkeleton />
        ) : error ? (
          <ErrorNote>{error}</ErrorNote>
        ) : !me?.staff_role ? (
          <EmptyNote icon={ShieldOff}>
            You don't have moderator access
          </EmptyNote>
        ) : (
          <ModerationProvider value={shared}>
            <Tabs value={tab} onValueChange={setTab} className="w-full gap-4">
              {/* Equal columns, down to icons alone where the widget is narrow */}
              <TabsList
                variant="line"
                className="grid h-10! w-full grid-cols-6 border-b p-0"
              >
                {TABS.map(({ value, label, icon: Icon }) => (
                  <TabsTrigger
                    key={value}
                    value={value}
                    aria-label={label}
                    title={label}
                    className="after:bg-tfs-brand-strong dark:after:bg-tfs-brand min-w-0 group-data-horizontal/tabs:after:bottom-0 hover:cursor-pointer"
                  >
                    <Icon />
                    <span className="hidden truncate @2xl:inline">{label}</span>
                    {value === "reports" && Boolean(openReports) && (
                      <span className="bg-tfs-brand-strong dark:bg-tfs-brand rounded-full px-1.5 text-xs font-semibold text-white dark:text-black">
                        {openReports}
                      </span>
                    )}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="reports">
                <ReportsPanel />
              </TabsContent>
              <TabsContent value="removed">
                <RemovedPanel />
              </TabsContent>
              <TabsContent value="comments">
                <CommentsPanel
                  userFilter={userFilter}
                  onUserFilter={setUserFilter}
                  threadFilter={threadFilter}
                  onThreadFilter={setThreadFilter}
                />
              </TabsContent>
              <TabsContent value="users">
                <UsersPanel />
              </TabsContent>
              <TabsContent value="bans">
                <BansPanel />
              </TabsContent>
              <TabsContent value="log">
                <LogPanel target={logTarget} onTarget={setLogTarget} />
              </TabsContent>
              <TabsContent value="settings">
                <AdminPanel />
              </TabsContent>
            </Tabs>

            <UserPanel user={openedUser} onClose={() => setOpenedUser(null)} />
          </ModerationProvider>
        )}
      </section>
    </TooltipProvider>
  );

  // Comments here show images as readers see them: inline from the community's image hosts, links from anywhere else
  return (
    <ImageHostsContext.Provider value={imageHosts}>
      {view}
    </ImageHostsContext.Provider>
  );
}
