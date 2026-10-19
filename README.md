# LE Auto Record

**Logic Encoder** — https://logicencoder.com  
GitHub: [`logicencoder/le-auto-record`](https://github.com/logicencoder/le-auto-record)

OpenPLi can keep a live TV buffer in the background, but it does **not** turn what you watched into normal movie files. **LE Auto Record** does: watch long enough, change channel or wait for the EPG programme to end, and a named `.ts` appears in your movie folder (disk or NAS).

## Install

```bash
cp -a LEAutoRecord /usr/lib/enigma2/python/Plugins/Extensions/
rm -f /usr/lib/enigma2/python/Plugins/Extensions/LEAutoRecord/*.pyc
```

Restart the Enigma2 GUI. Open:

**Menu → Plugins → LE Auto Record**

- **GREEN / OK** — save  
- **RED / EXIT** — cancel  
- **YELLOW** — About (Logic Encoder · https://logicencoder.com)

Enable auto-record, set **Folder for saved movies**, and keep OpenPLi’s own “Automatically start …” delay enabled so the live buffer actually runs.

## Features

| Feature | Role |
|--------|------|
| Auto-record of watched programmes | Writes normal `.ts` files |
| Setup GUI | Path, min zap length, EPG split, cleanup |
| CIFS mount watchdog | Remount NAS movie folder if it drops |

## Settings (GUI)

| Setting | Meaning |
|--------|---------|
| Enable auto-record | Master on/off |
| Save every watched programme | Write movie files from the buffer |
| Folder for saved movies | Destination for `.ts` files |
| New file when programme changes (EPG) | One file per show |
| Ignore zaps shorter than (minutes) | Surfing does not create junk |
| Seconds before EPG end to rotate file | Clean split between programmes |
| Cleanup check every | How often leftovers are tidied |
| Keep only newest N autosaves | Cap disk use (`0` = keep all) |
| Delete leftover buffers after (hours) | Remove orphan buffers (`0` = keep) |
| Stop saving if free space below (MB) | Protect the disk (`0` = off) |

## Requirements

- OpenPLi (tested: OpenPLi 9.2, VU+ Duo4K SE)
- Free space on the movie folder
- For network shares: working CIFS/automount

## Package layout

```text
LEAutoRecord/
  __init__.py
  plugin.py
```

## Limitations

- Needs the live buffer running (OpenPLi auto-start delay or manual start).
- On CIFS, buffers are moved (not hardlinked).
- Short zaps below the minimum minutes are discarded on purpose.

## Support

Logic Encoder — https://logicencoder.com  

## License

MIT — see [LICENSE](LICENSE). Keep author credit and the site link when redistributing.
