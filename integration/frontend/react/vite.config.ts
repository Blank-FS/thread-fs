import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import dts from "vite-plugin-dts";
import path from "node:path";

export default defineConfig({
  plugins: [
    react(),
    dts({
      tsconfigPath: "./tsconfig.build.json",
      entryRoot: "src",
      outDirs: "dist",
      insertTypesEntry: true,
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // This package is rendered both in the browser and during a host
      // app's SSR pass (e.g. Next.js). Its "browser" export condition
      // (which Vite resolves by default) calls `document.createElement`
      // at module top level to decode HTML entities via the native
      // parser - fine in a pure browser bundle, but it crashes immediately
      // when the module is evaluated on the server. Force the universal,
      // DOM-free implementation instead; it's slightly larger (pulls in a
      // static entity lookup table) but works in both environments. Scoped
      // to just this package so every other dependency keeps whichever
      // export condition Vite would normally pick for it.
      "decode-named-character-reference": path.resolve(
        __dirname,
        "node_modules/decode-named-character-reference/index.js",
      ),
    },
  },
  build: {
    // public/ only holds the test site's files, which don't belong in the package
    copyPublicDir: false,
    // ES modules only, one file per entry: the widget (index), and the markdown renderer and the editor alone
    // (markdown, editor: for hosts rendering and writing their other text like comments). What entries share (the
    // renderer, the editor and their libraries) goes in shared chunks, so a host's bundler downloads it once whichever
    // loads first.
    lib: {
      entry: {
        index: path.resolve(__dirname, "src/index.ts"),
        markdown: path.resolve(__dirname, "src/markdown.tsx"),
        editor: path.resolve(__dirname, "src/editor.tsx"),
      },
      formats: ["es"],
      fileName: (_format, entryName) => `${entryName}.js`,
      cssFileName: "threadfs-react",
    },
    cssCodeSplit: false,
    rollupOptions: {
      external: ["react", "react-dom", "react/jsx-runtime"],
      output: {
        chunkFileNames: "chunks/[name]-[hash].js",
      },
    },
  },
});
