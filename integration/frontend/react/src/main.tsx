import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";
import { ThreadFSComments } from "./components/ThreadFSComments";
import { ThemeProvider } from "./components/other/theme-provider";
import { ModeToggle } from "./components/other/mode-toggle";

function App() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl space-y-4 p-4">
      <ModeToggle />
      <ThreadFSComments
        apiBaseUrl="http://localhost:8000"
        communityKey="tfspub_demo_abc123"
        threadId="demo-thread"
        authToken="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwidXNlcm5hbWUiOiJFdmVyZ2FyZGVuIiwiYXZhdGFyX3VybCI6Imh0dHBzOi8vaW1nLmFuaXdvcmtzLm5ldC91c2Vycy9hdmF0YXIvMl9lZmYyYTQ2Yy0yNWRiLTRjMDEtYWZhMy0yODc2YjM4NjUwNmYiLCJpc3MiOiJkZW1vLXNpdGUiLCJhdWQiOiJ0aHJlYWRmcyIsImV4cCI6MTc4MDA0MDI3OX0.-OZIfakVcW_1DtJbYhqVnoPnVFVpZP6HRptLVZlDRmg"
        authorProfileUrl={(user) =>
          user.external_user_id ? `/users/${user.external_user_id}` : null
        }
        onAuthRequired={() => {
          const next = encodeURIComponent(window.location.href);
          window.location.href = `/login?next=${next}`;
        }}
      />
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
