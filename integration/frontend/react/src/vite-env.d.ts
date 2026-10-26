/// <reference types="vite/client" />

declare module "*.css";

interface ImportMetaEnv {
  readonly VITE_THREADFS_API_BASE_URL: string;
  readonly VITE_THREADFS_COMMUNITY_KEY: string;
  readonly VITE_THREADFS_THREAD_ID: string;
  readonly VITE_THREADFS_EXTERNAL_USER_ID: string;
  readonly VITE_THREADFS_AUTH_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
