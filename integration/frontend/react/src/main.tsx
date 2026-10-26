import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import React from "react";
import ReactDOM from "react-dom/client";
import { ThreadFSMyComments } from "./components/MyComments";
import { ThreadFSComments } from "./components/ThreadFSComments";
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

function App() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl space-y-4 p-2 sm:p-4">
      <ModeToggle />
      <Tabs defaultValue="ThreadFSComments" className="w-full">
        <TabsList>
          <TabsTrigger value="ThreadFSComments" className="w-36">
            Discussion
          </TabsTrigger>
          <TabsTrigger value="ThreadFSMyComments" className="w-36">
            Comments
          </TabsTrigger>
        </TabsList>
        <TabsContent value="ThreadFSComments">
          <ThreadFSComments
            apiBaseUrl={apiBaseUrl}
            communityKey={communityKey}
            threadId={threadId}
            authToken={authToken}
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
      </Tabs>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);
