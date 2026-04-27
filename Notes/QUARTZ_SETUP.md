# Quartz Setup

The `quartz/` directory is **not tracked by git** (see `.gitignore`). Clone it manually after checking out this repo.

## First-time setup

```bash
# 1. Clone Quartz into the Notes/quartz/ folder
git clone https://github.com/jackyzha0/quartz.git quartz

# 2. Install dependencies
cd quartz
npm install
```

## Generate the site

Run the batch script from the `Notes/` folder:

```bat
generate_static_site.bat
```

This will:
1. Clear `quartz/content/`
2. Copy the `FunRad/` Obsidian vault into `quartz/content/`
3. Build the static site with `npx quartz build`
4. Copy the result to `public/`

## Quartz configuration

`quartz/quartz.config.ts` and `quartz/quartz.layout.ts` control theming and plugins.
See [quartz.jzhao.xyz](https://quartz.jzhao.xyz) for documentation.

> **Tip:** To track your Quartz config customisations in this repo, copy the two
> config files up to `Notes/` and symlink them, or commit the entire `quartz/`
> folder — just be aware it brings in `node_modules` unless you keep the
> `.gitignore` entries above.
