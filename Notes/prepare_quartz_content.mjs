// Quartz's "shortest" link strategy expects vault-root paths for Markdown
// links. Convert relative paths only in the copied content, keeping the
// original notes compatible with Obsidian and ordinary Markdown viewers.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const content = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "quartz/content");
let rewritten = 0;

function prepare(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) continue;
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      prepare(file);
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      const original = fs.readFileSync(file, "utf8");
      const updated = original.replace(/\]\(([^\n)]+)\)/g, (match, url) => {
        if (/^[a-z][\w+.-]*:/i.test(url) || url.startsWith("/") || url.startsWith("#")) return match;
        const [rawPath, ...fragment] = url.split("#");
        const target = path.resolve(directory, decodeURIComponent(rawPath));
        const relative = path.relative(content, target);
        if (relative.startsWith("..") || path.isAbsolute(relative) || !fs.existsSync(target)) return match;
        rewritten++;
        return `](${relative.split(path.sep).join("/").replaceAll(" ", "%20")}${fragment.length ? "#" + fragment.join("#") : ""})`;
      });
      if (updated !== original) fs.writeFileSync(file, updated, "utf8");
    }
  }
}

prepare(content);
console.log(`Prepared ${rewritten} local Markdown links for Quartz.`);
