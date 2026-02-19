# Static Site Publisher

Upload Staatic-exported static sites to FTP via WinSCP, sync DokuWiki content, and create dated archives.

## Overview

The publishing workflow for **floriandheer.com** and **hyphen-v.com** involves:

1. Exporting WordPress to static HTML via Staatic (in Laragon)
2. Uploading the export to the live server via FTP
3. Synchronizing DokuWiki content (floriandheer.com only)
4. Creating a dated zip archive

This script automates steps 2-4.

## Prerequisites

- **WinSCP** installed (portable or full install) - [winscp.net](https://winscp.net/)
- FTP/SFTP credentials for each site
- Staatic export already completed in the `03_publish/{site}` folder

## Configuration

On first launch, open **Settings** to configure:

- **FTP credentials** (host, username, password, remote path) for each site
- **WinSCP path** - auto-detected from common install locations, or set manually
- **Export directory** - defaults derived from work drive (`I:\Web\_Personal\{site}\03_publish\{site}`)
- **Wiki latest directory** - (floriandheer only) local copy of wiki content

Configuration is stored at:
```
%LOCALAPPDATA%\PipelineManager\web_publish_config.json
```

## Workflow

### floriandheer.com (with DokuWiki)

| Step | Action | Details |
|------|--------|---------|
| 1 | **Validate** | Check paths, WinSCP, FTP credentials |
| 2 | **FTP Upload** | `synchronize remote` excluding `/wiki/` |
| 3 | **Copy wiki** | Copy `_wiki_latest` into export dir as `wiki/` |
| 4 | **Sync wiki** | `synchronize local` to pull online DokuWiki changes |
| 5 | **Update _wiki_latest** | Copy synced wiki back to `_wiki_latest` |
| 6 | **Archive** | Zip entire export (static + wiki) |

### hyphen-v.com (no wiki)

| Step | Action | Details |
|------|--------|---------|
| 1 | **Validate** | Check paths, WinSCP, FTP credentials |
| 2 | **FTP Upload** | `synchronize remote` (full) |
| 3 | **Archive** | Zip export directory |

## Wiki Management

The DokuWiki on floriandheer.com is maintained online only. The `_wiki_latest` folder stores a local snapshot used to keep the static export in sync.

### Folder structure

```
I:\Web\_Personal\floriandheer\
    _wiki_latest\           <-- local wiki snapshot
        data/
        lib/
        conf/
        ...
    03_publish\floriandheer\
        index.html          <-- Staatic export
        ...
        wiki\               <-- copied from _wiki_latest, then synced
            data/
            lib/
            ...
```

### Sync cycle

1. The Staatic export never includes wiki content
2. Script copies `_wiki_latest` into the export as `wiki/`
3. Script pulls any online changes via `synchronize local`
4. Updated wiki is copied back to `_wiki_latest` for next time

### First-time setup

If `_wiki_latest` doesn't exist, the script prompts you to either:
- **Download from server** - pulls wiki content from the live site
- **Browse folder** - select an existing local wiki folder

## Archive Structure

Archives are created under the configured archive path:

```
D:\_work\Archive\Web\
    floriandheer\
        floriandheer_2026-02-19.zip
        floriandheer_2026-01-15.zip
    hyphen-v\
        hyphen-v_2026-02-19.zip
```

Each zip contains the full export directory (including wiki for floriandheer).

## Troubleshooting

**WinSCP not found**
- Install WinSCP and ensure `winscp.com` is in the install directory
- Or set the path manually in Settings

**FTP upload fails**
- Verify credentials in Settings using the "Test Connection" button
- Check that the remote path is correct
- Review the output log for WinSCP error messages

**Wiki sync fails**
- Ensure the wiki remote path matches the server layout (default: `/wiki`)
- Check that DokuWiki is accessible on the live server

**Archive too large**
- The script zips the entire export directory including wiki
- Clean up unnecessary files from the export before publishing
