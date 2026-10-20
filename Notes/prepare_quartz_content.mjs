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
      let original = fs.readFileSync(file, "utf8");
      // Report.md and Report.html would both emit Report.html in Quartz.
      // Rename only the copied interactive asset and its report link.
      const sibling = file.slice(0, -3) + ".html";
      if (fs.existsSync(sibling)) {
        const interactive = file.slice(0, -3) + ".interactive.html";
        fs.renameSync(sibling, interactive);
        for (const name of [path.basename(sibling), encodeURI(path.basename(sibling))]) {
          original = original.replaceAll(`](${name})`, `](${encodeURI(path.basename(interactive))})`);
        }
      }
      const updated = original.replace(/\]\(([^\n)]+)\)/g, (match, url) => {
        if (/^[a-z][\w+.-]*:/i.test(url) || url.startsWith("/") || url.startsWith("#")) return match;
        const [rawPath, ...fragment] = url.split("#");
        const target = path.resolve(directory, decodeURIComponent(rawPath));
        const relative = path.relative(content, target);
        if (relative.startsWith("..") || path.isAbsolute(relative) || !fs.existsSync(target)) return match;
        rewritten++;
        return `](${relative.split(path.sep).join("/").replaceAll(" ", "%20")}${fragment.length ? "#" + fragment.join("#") : ""})`;
      });
      if (updated !== fs.readFileSync(file, "utf8")) fs.writeFileSync(file, updated, "utf8");
    }
  }
}

prepare(content);
console.log(`Prepared ${rewritten} local Markdown links for Quartz.`);
