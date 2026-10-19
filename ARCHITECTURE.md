# LE Auto Record — architecture

**Logic Encoder** — https://logicencoder.com

## Role

OpenPLi Extension that saves the live TV buffer as normal recordings, with a Setup GUI and a CIFS remount watchdog for NAS movie folders.

## Install path

```text
/usr/lib/enigma2/python/Plugins/Extensions/LEAutoRecord/
```

User-facing and package name: **LE Auto Record** / `LEAutoRecord`.

## Runtime flow

1. `Plugins()` registers autostart plus Plugin / Extensions menu entries.
2. On GUI start, hooks patch the live-buffer save/start/stop callbacks.
3. When the buffer starts, the plugin arms save flags and optional EPG split.
4. On zap / stop / event boundary, if watched duration ≥ `minminutes`, the buffer becomes a named `.ts` under the movie folder.
5. Cleanup removes orphan buffer leftovers and enforces max-count / free-space rules.
6. If the save directory is CIFS and becomes unwritable, `_mount_watchdog` remounts using `/etc/enigma2/automounts.xml` when available.
7. Stock OpenPLi `AutoMount.makeHDDlink` is replaced so a NAS linked as `/media/hdd` does not create a `movie/` subdirectory; `Harddisk.createMovieDir` is a no-op.

## Configuration

| Namespace | Purpose |
|-----------|---------|
| `config.plugins.lear.*` | Plugin enable, min minutes, EPG margin |
| `config.timeshift.*` | OpenATV-compatible autorecord / path / split / cleanup (Enigma2 platform keys) |
| `config.usage.timeshift_path` / `default_path` | Aligned with movie folder from Setup |

## Logging

`/tmp/lear.log` on the receiver.

## Files

| File | Responsibility |
|------|----------------|
| `LEAutoRecord/plugin.py` | Hooks, cleanup, CIFS watchdog, Setup UI |
| `LEAutoRecord/__init__.py` | Package marker |
