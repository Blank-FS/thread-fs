import React from "react";
import ReactDOM from "react-dom/client";
import { ThreadFSComments } from "./components/ThreadFSComments";
import { ModeToggle } from "./components/other/mode-toggle";
import { ThemeProvider } from "./components/other/theme-provider";
import "./styles.css";

function App() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl space-y-4 p-4">
      <ModeToggle />
      <ThreadFSComments
        apiBaseUrl="http://localhost:8001"
        communityKey="tfspub_demo_abc123"
        threadId="demo-thread"
        authToken="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vLXVzZXItMSIsInVzZXJuYW1lIjoiQmxhbmsiLCJhdmF0YXJfdXJsIjoiaHR0cHM6Ly9hcGkuZGljZWJlYXIuY29tLzgueC9pbml0aWFscy9zdmc_c2VlZD1CbGFuayIsImlzcyI6ImRlbW8tc2l0ZSIsImF1ZCI6InRocmVhZGZzIiwiZXhwIjoxNzgyNjE5Nzg3fQ.gb8WldNhykhgz4du6G_6HjscXHeXG3ovrMDgwxY74dg"
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
