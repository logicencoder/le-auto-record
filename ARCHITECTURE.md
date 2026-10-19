# LE Auto Record — architecture

**Logic Encoder** — https://logicencoder.com

## Role

OpenPLi Extension that saves the live TV buffer as normal recordings, with a Setup GUI and a CIFS remount watchdog for NAS movie folders.

## Install path

```text
/usr/lib/enigma2/python/Plugins/Extensions/LEAutoRecord/
```

User-facing and package name: **LE Auto Record** / `LEAutoRecord`.

## Why some engine symbols still say “timeshift”

Enigma2’s only live-buffer API and leftover buffer filenames still use that word (`InfoBarTimeshift`, `timeshift.*` on disk, OpenPLi `config.usage.timeshift_path`, OpenATV-compatible `config.timeshift.*`). Those are platform names, not the product name. The product is **LE Auto Record**.

## Runtime flow

1. `Plugins()` registers autostart plus Plugin / Extensions menu entries.
2. On GUI start, hooks patch the live-buffer save/start/stop callbacks.
3. When the buffer starts, the plugin arms save flags and optional EPG split.
4. On zap / stop / event boundary, if watched duration ≥ `minminutes`, the buffer becomes a named `.ts` under the movie folder.
5. Cleanup removes orphan buffer leftovers and enforces max-count / free-space rules.
6. If the save directory is CIFS and becomes unwritable, `_mount_watchdog` remounts using `/etc/enigma2/automounts.xml` when available.

## Configuration

| Namespace | Purpose |
|-----------|---------|
| `config.plugins.lear.*` | Plugin enable, min minutes, EPG margin |
| `config.timeshift.*` | OpenATV-compatible autorecord / path / split / cleanup (platform keys) |
| `config.usage.timeshift_path` / `default_path` | Aligned with movie folder from Setup |

Older installs used `config.plugins.leautots.*`; values are migrated into `lear` on load.

## Logging

`/tmp/lear.log` on the receiver.

## Out of scope

- Permanent OSD clock (PermanentClock)
- Volume / mute persistence
- SoftCAM / streaming / EPG grabbers

## Files

| File | Responsibility |
|------|----------------|
| `LEAutoRecord/plugin.py` | Hooks, cleanup, CIFS watchdog, Setup UI |
| `LEAutoRecord/__init__.py` | Package marker |
