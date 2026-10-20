// Copy tracked and nonignored vault files, including new report snapshots.
// Destination cleanup is performed by generate_static_site.bat.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const notes = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(notes);
const destination = path.join(notes, "quartz/content");
const prefix = "Notes/FunRad/";
const files = execFileSync("git", ["ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", prefix], { cwd: root, encoding: "utf8" }).split("\0").filter(Boolean);
let copied = 0;
for (const file of new Set(files)) {
  if (!file.startsWith(prefix)) throw new Error(`Unexpected vault path: ${file}`);
  const source = path.join(root, file);
  if (!fs.existsSync(source)) continue; // Deleted tracked notes.
  const target = path.resolve(destination, file.slice(prefix.length));
  const relative = path.relative(destination, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) throw new Error(`Path outside content: ${file}`);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
  copied++;
}
console.log(`Copied ${copied} tracked/nonignored vault files to Quartz.`);
