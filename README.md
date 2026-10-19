# LE Auto Record

**Logic Encoder** — https://logicencoder.com  
GitHub: [`logicencoder/le-auto-record`](https://github.com/logicencoder/le-auto-record)

OpenPLi can start a background TV buffer, but it does not turn what you actually watched into normal movie files. On OpenATV that “save every watched programme” behaviour exists in the image. **LE Auto Record** brings the same outcome to OpenPLi: watch TV, change channel or wait for the EPG event to end, and a named `.ts` recording appears in your movie folder (local disk or NAS).

The box still uses its timeshift engine under the hood — that is the only buffer OpenPLi has. The product is automatic recording, not a pause-live-TV utility.

## Install

On the receiver (SSH or file manager), copy the plugin folder:

```bash
# from this repository
cp -a LeAutoTimeshift /usr/lib/enigma2/python/Plugins/Extensions/
rm -f /usr/lib/enigma2/python/Plugins/Extensions/LeAutoTimeshift/*.pyc
```

Restart the Enigma2 GUI (Menu → Standby / restart GUI, or reboot the box).

Open:

**Menu → Plugins → LE Auto Record**  
(also under Extensions)

- **GREEN / OK** — save  
- **RED / EXIT** — cancel  
- **YELLOW** — About (author + https://logicencoder.com)

Set **Folder for saved movies** to your recording path, enable auto-record, and leave OpenPLi’s own “Automatically start timeshift after …” enabled so the buffer actually runs.

## What is included

| Feature | Role |
|--------|------|
| Auto-record of watched programmes | Core — writes normal `.ts` files |
| Setup GUI | Configure path, min zap length, EPG split, cleanup |
| CIFS mount watchdog | If a NAS movie folder drops, try remount so recording can continue |
| Volume / mute persistence | **Not included** |
| Permanent OSD clock | **Not included** — use stock **PermanentClock** |

## Settings (GUI)

| Setting | Meaning |
|--------|---------|
| Enable auto-record | Master on/off |
| Save every watched programme | Write movie files from the buffer |
| Folder for saved movies | Destination for `.ts` files |
| New file when programme changes (EPG) | One file per show |
| Ignore zaps shorter than (minutes) | Channel surfing does not create junk |
| Seconds before EPG end to rotate file | Clean split between programmes |
| Cleanup check every | How often leftovers are tidied |
| Keep only newest N autosaves | Cap disk use (`0` = keep all) |
| Delete leftover buffers after (hours) | Remove orphan buffers (`0` = keep) |
| Stop saving if free space below (MB) | Protect the disk (`0` = off) |

## Requirements

- OpenPLi (developed/tested on OpenPLi 9.2, VU+ Duo4K SE)
- Enough free space on the movie folder
- For network shares: a working CIFS/automount setup

## Package layout

```text
LeAutoTimeshift/          # install this folder under Extensions/
  __init__.py
  plugin.py               # autostart hooks + Setup screen
```

## Limitations

- Needs the background buffer running (OpenPLi timeshift auto-start or manual start).
- Hardlinks used on OpenATV are not used here; on CIFS the plugin mark/stop/moves the buffer instead.
- Short zaps below the configured minimum minutes are discarded on purpose.

## Support

Logic Encoder — https://logicencoder.com  
Issues: use the GitHub repository issue tracker.

## License

MIT — see [LICENSE](LICENSE). Keep author credit and the site link in the plugin About screen when redistributing.
