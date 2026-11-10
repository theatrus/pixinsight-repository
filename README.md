# pixinsight-repository

The **theatr.us PixInsight update repository**, served at
**https://pixinsight.theatr.us/**. It currently publishes the
**Foraxx Palette Utility** (the Foraxx palette is
[The Coldest Nights](https://thecoldestnights.com/)' dynamic narrowband combination) (source: [theatrus/foraxx-palette-utility](https://github.com/theatrus/foraxx-palette-utility)),
the V8 rewrite for PixInsight 1.9.4 and later. The original 1.16 for
PixInsight 1.8.9-3 to 1.9.3 was withdrawn in November 2026; it is still
available from Paul Hancock's own repository, `https://foraxxpaletteutility.com/FPU/`.

PixInsight users add `https://pixinsight.theatr.us/` under
Resources > Updates > Manage Repositories. The earlier address
`https://pixinsight.psf-guard.com/` is a permanent alias of the same files.

## Layout

```
packages.json      # what is published: archives, titles, platform version ranges
packages/*.zip     # the package archives (src/scripts/<Name>/... trees)
updates.xri        # the signed index, when present (see Signing)
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
`build-index.py --publish /www/pixinsight.theatr.us`, which copies the
archives first, then `index.html`, then `updates.xri` (the committed signed
one, or a fresh unsigned one if none is committed), each swapped in
atomically, and finally removes archives that are no longer listed.

```
https://pixinsight.theatr.us/updates.xri     # the index PixInsight reads
https://pixinsight.theatr.us/<archive>.zip   # the packages
```

## Adding or updating a package

1. Build the archive in the script's own repository (for Foraxx,
   `./build.sh` writes it to `dist/`).
2. Copy it into `packages/` under a new, unique name.
3. Add or update its entry in `packages.json`. To replace a version, point the
   existing entry at the new archive and bump the title and release date.
4. Write and sign the index (see Signing), run `./build-index.py --check`,
   then push to `main`.

For Foraxx, `./release.sh` in foraxx-palette-utility does all of this.

## Signing

The index is signed as the Certified PixInsight Developer `theatrus`, so
PixInsight installs from it without the unsigned-repository warning. The
signature is embedded in `updates.xri`, which is committed here:

```
./build-index.py --xri > updates.xri
<foraxx-palette-utility>/scripts/pisign.py sign updates.xri --key-file ~/.pixinsight-signing/theatrus.ed25519
```

`build-index.py --check` and `--publish` refuse a committed `updates.xri`
that is not exactly the `--xri` output plus its `Signature` line, so editing
`packages.json` means signing again. The server never sees the key. Delete
`updates.xri` to go back to an unsigned index.

Format reference:
https://pixinsight.com/doc/docs/PIRepositoryReference/PIRepositoryReference.html
