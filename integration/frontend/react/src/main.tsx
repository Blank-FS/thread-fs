import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import React, { useCallback, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { ThreadFSMyComments } from "./components/MyComments";
import { ThreadFSComments } from "./components/ThreadFSComments";
import { ThreadFSModeration } from "./components/ThreadFSModeration";
import { ModeToggle } from "./components/other/mode-toggle";
import { ThemeProvider } from "./components/other/theme-provider";
import { commentHash, commentIdFromHash } from "./lib/commentLinks";
import "./styles.css";

type DemoUser = {
  id: string;
  name: string;
  role: string | null;
  token: string;
};

// Test-site config comes from .env (see .env.example).
const env = import.meta.env;
const apiBaseUrl = env.VITE_THREADFS_API_BASE_URL;
const communityKey = env.VITE_THREADFS_COMMUNITY_KEY;
const threadId = env.VITE_THREADFS_THREAD_ID;
const demoUsers: DemoUser[] = JSON.parse(env.VITE_THREADFS_DEMO_USERS || "[]");

const SIGNED_OUT = "signed-out";
const USER_STORAGE_KEY = "threadfs-demo-user";

function storedUserId() {
  const id = localStorage.getItem(USER_STORAGE_KEY);
  return demoUsers.some((user) => user.id === id) ? id! : SIGNED_OUT;
}

// The comment a #c-<id> link points at, kept in step with the address bar
function useLinkedComment() {
  const [id, setId] = useState(() => commentIdFromHash(location.hash));
  useEffect(() => {
    const update = () => setId(commentIdFromHash(location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return id;
}

function App() {
  const [userId, setUserId] = useState(storedUserId);
  const linkedComment = useLinkedComment();
  // Following a comment link (from the Comments tab, say) shows the discussion it points into
  const [tab, setTab] = useState("ThreadFSComments");
  useEffect(() => {
    if (linkedComment) setTab("ThreadFSComments");
  }, [linkedComment]);
  const user = demoUsers.find(({ id }) => id === userId) ?? null;
  const token = user?.token ?? null;
  const getDemoToken = useCallback(async () => token, [token]);

  function switchUser(id: string) {
    localStorage.setItem(USER_STORAGE_KEY, id);
    setUserId(id);
  }

  return (
    // The widget's styles stop at .threadfs-root, so here it covers the whole page, not just the column
    <div className="threadfs-root bg-background text-foreground min-h-screen">
      <main className="mx-auto max-w-3xl space-y-4 p-2 sm:p-4">
        <div className="flex items-center gap-2">
          <ModeToggle />
          <Select value={userId} onValueChange={switchUser}>
            <SelectTrigger aria-label="Viewing as" className="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SIGNED_OUT}>Signed out</SelectItem>
              {demoUsers.map(({ id, name, role }) => (
                <SelectItem key={id} value={id}>
                  {name} ({role ?? "user"})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="ThreadFSComments" className="flex-1">
              Discussion
            </TabsTrigger>
            <TabsTrigger value="ThreadFSMyComments" className="flex-1">
              Comments
            </TabsTrigger>
            <TabsTrigger value="ThreadFSModeration" className="flex-1">
              Moderation
            </TabsTrigger>
          </TabsList>
          {/* Keyed by user, so a switch starts each widget fresh, as a new page load would */}
          <TabsContent value="ThreadFSComments">
            <ThreadFSComments
              key={userId}
              apiBaseUrl={apiBaseUrl}
              communityKey={communityKey}
              threadId={threadId}
              getAuthToken={getDemoToken}
              focusCommentId={linkedComment}
              commentUrl={(id) =>
                `${location.origin}${location.pathname}${commentHash(id)}`
              }
              authorProfileUrl={(author) =>
                author.external_user_id
                  ? `/users/${author.external_user_id}`
                  : null
              }
              onAuthRequired={() =>
                window.alert("Pick a user from the menu to sign in")
              }
            />
          </TabsContent>
          <TabsContent value="ThreadFSMyComments">
            <ThreadFSMyComments
              key={userId}
              apiBaseUrl={apiBaseUrl}
              communityKey={communityKey}
              externalUserId={user?.id}
              authToken={token}
              authorProfileUrl={(author) =>
                author.external_user_id
                  ? `/users/${author.external_user_id}`
                  : null
              }
            />
          </TabsContent>
          <TabsContent value="ThreadFSModeration">
            <ThreadFSModeration
              key={userId}
              apiBaseUrl={apiBaseUrl}
              communityKey={communityKey}
              authToken={token}
            />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);
