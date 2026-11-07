import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import React from "react";
import ReactDOM from "react-dom/client";
import { ThreadFSMyComments } from "./components/MyComments";
import { ThreadFSComments } from "./components/ThreadFSComments";
import { ThreadFSModeration } from "./components/ThreadFSModeration";
import { ModeToggle } from "./components/other/mode-toggle";
import { ThemeProvider } from "./components/other/theme-provider";
import "./styles.css";

// Test-site config comes from .env (see .env.example).
const env = import.meta.env;
const apiBaseUrl = env.VITE_THREADFS_API_BASE_URL;
const communityKey = env.VITE_THREADFS_COMMUNITY_KEY;
const threadId = env.VITE_THREADFS_THREAD_ID;
const externalUserId = env.VITE_THREADFS_EXTERNAL_USER_ID;
const authToken = env.VITE_THREADFS_AUTH_TOKEN || undefined;
const getDemoToken = async () => authToken ?? null;

function App() {
  return (
    // The widget's styles stop at .threadfs-root, so here it covers the whole page, not just the column
    <div className="threadfs-root bg-background text-foreground min-h-screen">
      <main className="mx-auto max-w-3xl space-y-4 p-2 sm:p-4">
        <ModeToggle />
        <Tabs defaultValue="ThreadFSComments" className="w-full">
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
          <TabsContent value="ThreadFSComments">
            <ThreadFSComments
              apiBaseUrl={apiBaseUrl}
              communityKey={communityKey}
              threadId={threadId}
              getAuthToken={getDemoToken}
              authorProfileUrl={(user) =>
                user.external_user_id ? `/users/${user.external_user_id}` : null
              }
              onAuthRequired={() => {
                const next = encodeURIComponent(window.location.href);
                window.location.href = `/login?next=${next}`;
              }}
            />
          </TabsContent>
          <TabsContent value="ThreadFSMyComments">
            <ThreadFSMyComments
              apiBaseUrl={apiBaseUrl}
              communityKey={communityKey}
              externalUserId={externalUserId}
              authToken={authToken}
            />
          </TabsContent>
          <TabsContent value="ThreadFSModeration">
            <ThreadFSModeration
              apiBaseUrl={apiBaseUrl}
              communityKey={communityKey}
              authToken={env.VITE_THREADFS_MODERATOR_TOKEN || authToken}
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
