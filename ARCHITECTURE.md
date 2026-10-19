# LE Auto Record — architecture

**Logic Encoder** — https://logicencoder.com

## Role

OpenPLi Extension that ports OpenATV-style “save watched buffer as recording” onto the stock OpenPLi `InfoBarTimeshift` engine, with a Setup GUI and a CIFS remount watchdog for NAS movie folders.

## Install path

```text
/usr/lib/enigma2/python/Plugins/Extensions/LeAutoTimeshift/
```

User-facing name: **LE Auto Record**. Folder name stays `LeAutoTimeshift` for Enigma2 Extension path compatibility.

## Runtime flow

1. `Plugins()` registers `WHERE_AUTOSTART` plus Plugin / Extensions menu entries.
2. On GUI start, `autostart` patches:
   - `InfoBarTimeshift.startTimeshift`
   - `InfoBarTimeshift.saveTimeshiftFileForEvent`
   - `InfoBarTimeshift.saveTimeshiftFiles`
   - `InfoBarTimeshift.stopTimeshiftcheckTimeshiftRunningCallback`
3. When timeshift starts, the plugin arms save flags and (optionally) an EPG end timer (`fileSplitting`).
4. On zap / stop / event boundary, if the watched duration is at least `minminutes`, the buffer is marked and moved into a named `.ts` under `recordingPath`.
5. A cleanup timer removes orphan `timeshift.*` leftovers and enforces max-count / free-space rules.
6. If the save directory is a CIFS mount and becomes unwritable, `_mount_watchdog` remounts using `/etc/enigma2/automounts.xml` credentials when available.

## Configuration namespaces

| Namespace | Purpose |
|-----------|---------|
| `config.timeshift.*` | OpenATV-compatible autorecord / path / split / cleanup |
| `config.plugins.leautots.*` | Plugin enable, min minutes, EPG margin |
| `config.usage.timeshift_path` / `default_path` | Aligned with movie folder when saved from Setup |

## Logging

Diagnostic lines append to `/tmp/leautots.log` on the receiver.

## Out of scope

- Permanent OSD clock (use PermanentClock).
- Volume / mute persistence.
- SoftCAM / streaming / EPG grabbers.
- Changing OpenPLi core images.

## Files

| File | Responsibility |
|------|----------------|
| `LeAutoTimeshift/plugin.py` | Config registration, patches, cleanup, CIFS watchdog, Setup UI |
| `LeAutoTimeshift/__init__.py` | Package marker |
