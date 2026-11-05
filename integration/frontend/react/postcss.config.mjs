import scopeToWidget from "./postcss-scope.mjs";

export default {
  plugins: [
    (await import("@tailwindcss/postcss")).default(),
    (await import("autoprefixer")).default(),
    scopeToWidget(),
  ],
};
