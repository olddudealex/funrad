# Generated report snapshots

Keep the published report sets in Git: Markdown, JSON results, overview PNG, and standalone interactive HTML. Recognized names are `* Results.*` (the existing report) and `*.results.*` (the simulator's current naming convention), with extensions `md`, `json`, `png`, and `html`.

These are snapshots: regenerate them deliberately when publishing simulation results. Their engine version and configuration hash identify the run; committing outputs alone does not archive the exact simulator source or configuration.

Browser profiles, experimental HTML pages, and UI screenshots in this folder remain ignored. They are not report inputs.

The static-site build copies tracked and nonignored vault files. In the copied Quartz content only, a standalone HTML report sharing a Markdown basename receives an `.interactive.html` suffix, and its report link is updated. This keeps the rendered Markdown page and interactive report separate. The original Obsidian files retain their names.
