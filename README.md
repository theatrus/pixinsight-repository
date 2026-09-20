# pixinsight-repository

The **theatr.us PixInsight update repository**, served at
**https://pixinsight.psf-guard.com/**. It currently publishes the
**Foraxx Palette Utility** (source: [theatrus/foraxx-palette-utility](https://github.com/theatrus/foraxx-palette-utility)),
both the V8 rewrite for PixInsight 1.9.4+ and the original 1.16 for older
1.8.9-3 to 1.9.3 installs.

PixInsight users add `https://pixinsight.psf-guard.com/` under
Resources > Updates > Manage Repositories.

## Layout

```
packages.json      # what is published: archives, titles, platform version ranges
packages/*.zip     # the package archives (src/scripts/<Name>/... trees)
index.html         # the landing page
build-index.py     # generates updates.xri and lays out the served tree
```

`packages.json` holds one entry per archive. Each entry lists the archive
path, the package type, a release date (`YYYYMMDD`), a title, description
paragraphs, and the platforms it applies to. A platform's `version` is an
inclusive PixInsight version range such as `1.9.4:1.9.99`. Archives are served
flat at the repository root, since PixInsight resolves `fileName` relative to
the repository URL. Every package also carries `serverURL`, the repository's
own URL, because PixInsight resolves `fileName` against the repository URL as
typed and a bare `https://host` (no trailing slash) turns the file name into a
host name.

## How it's published

Pushing to `main` triggers a flotswarm push-to-deploy on **ec2admin**
(`deploy-pixinsight-repo`): it `git reset`s this checkout and runs
`build-index.py --publish /www/pixinsight.psf-guard.com`, which copies the
archives first, then `index.html`, then `updates.xri` with fresh SHA-1
digests, each swapped in atomically, and finally removes archives that are no
longer listed.

```
https://pixinsight.psf-guard.com/updates.xri     # the index PixInsight reads
https://pixinsight.psf-guard.com/<archive>.zip   # the packages
```

## Adding or updating a package

1. Build the archive in the script's own repository (for Foraxx,
   `./build.sh` writes it to `dist/`).
2. Copy it into `packages/` under a new, unique name.
3. Add or update its entry in `packages.json`. To replace a version, point the
   existing entry at the new archive and bump the title and release date.
4. Run `./build-index.py --check`, then push to `main`.

The index is not code-signed. PixInsight installs from unsigned repositories
with a warning; signing needs a Certified PixInsight Developer identity.

Format reference:
https://pixinsight.com/doc/docs/PIRepositoryReference/PIRepositoryReference.html
