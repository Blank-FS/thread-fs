// Keeps the stylesheet inside the widget. It's a complete Tailwind build, so left alone its reset, theme variables and
// utilities apply to the whole host page, and its .hidden can beat a host's md:flex. This moves every rule under
// .threadfs-root, which also gives them the specificity to win inside the widget. Anything rendered outside it (a
// popup in a portal) needs the class too: see the ui components.
const ROOT = ".threadfs-root";

const scope = (selector) => {
  const s = selector.trim();

  if (s.includes(ROOT)) return [s];
  if (s === ":root" || s === ":host" || s === "html" || s === "body") return [ROOT];
  if (s === ".dark") return [`.dark ${ROOT}`, `.dark${ROOT}`];
  if (s === "*") return [ROOT, `${ROOT} *`];
  if (s.startsWith(".")) return [`${ROOT} ${s}`, `${ROOT}${s}`];
  return [`${ROOT} ${s}`];
};

const isScoped = (rule) => {
  for (let parent = rule.parent; parent; parent = parent.parent) {
    if (parent.type === "rule") return false; // nested: follows its parent
    if (parent.type === "atrule") {
      if (/keyframes$/i.test(parent.name)) return false;
      if (parent.name === "layer" && parent.params === "properties") return false;
    }
  }
  return true;
};

export default function scopeToWidget() {
  return {
    postcssPlugin: "threadfs-scope",
    OnceExit(root) {
      root.walkRules((rule) => {
        if (!isScoped(rule)) return;

        // A host's page background isn't the widget's to set
        if (rule.selectors.includes("body")) {
          rule.walkDecls(/^background/, (decl) => decl.remove());
        }

        rule.selectors = [...new Set(rule.selectors.flatMap(scope))];
      });
    },
  };
}
