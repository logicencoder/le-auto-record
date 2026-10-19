# LE Auto Record (package: LeAutoTimeshift)
# Logic Encoder — https://logicencoder.com
#
# What this solves:
#   OpenPLi can start a background TV buffer, but it does NOT turn what you
#   watched into normal movie files. On OpenATV that "save every watched show"
#   behaviour exists built-in. This plugin brings the same result to OpenPLi:
#   watch TV -> on channel change / end of programme -> named .ts on disk/NAS.
#
# Internally it still uses Enigma2's timeshift engine (that is the only buffer
# OpenPLi has). Users should ignore that word — the product is auto-record.
#
# Author: Logic Encoder (logicencoder) — https://logicencoder.com

import os
from time import time, strftime

try:
	from Components.Language import _
except Exception:
	def _(s):
		return s

from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.config import (
	ConfigInteger,
	ConfigSelection,
	ConfigSubsection,
	ConfigText,
	ConfigYesNo,
	config,
	configfile,
	getConfigListEntry,
)
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.UsageConfig import defaultMoviePath
from Plugins.Plugin import PluginDescriptor
from Screens.InfoBarGenerics import InfoBarTimeshift
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.Directories import getRecordingFilename

# ---------------------------------------------------------------------------
# config - register the OpenATV keys (absent in OpenPLi; saved values from a
# previous OpenATV install in /etc/enigma2/settings are picked up at load)
# ---------------------------------------------------------------------------
if not hasattr(config, "timeshift") or not isinstance(getattr(config, "timeshift", None), ConfigSubsection):
	config.timeshift = ConfigSubsection()
if not hasattr(config.timeshift, "autorecord"):
	config.timeshift.autorecord = ConfigYesNo(default=True)
if not hasattr(config.timeshift, "recordingPath"):
	config.timeshift.recordingPath = ConfigText(default="", fixed_size=False)
if not hasattr(config.timeshift, "path"):
	config.timeshift.path = ConfigText(default="", fixed_size=False)
if not hasattr(config.timeshift, "fileSplitting"):
	config.timeshift.fileSplitting = ConfigYesNo(default=True)
if not hasattr(config.timeshift, "deleteAfterZap"):
	config.timeshift.deleteAfterZap = ConfigYesNo(default=True)
if not hasattr(config.timeshift, "checkEvents"):
	config.timeshift.checkEvents = ConfigSelection(default=0, choices=[(0, "Disabled")] + [(x, "%d min" % x) for x in (15, 30, 60, 120, 240, 480)])
if not hasattr(config.timeshift, "maxEvents"):
	config.timeshift.maxEvents = ConfigInteger(default=12, limits=(0, 999))
if not hasattr(config.timeshift, "maxHours"):
	config.timeshift.maxHours = ConfigInteger(default=0, limits=(0, 999))
if not hasattr(config.timeshift, "checkFreeSpace"):
	config.timeshift.checkFreeSpace = ConfigInteger(default=0, limits=(0, 65536))

config.plugins.leautots = ConfigSubsection()
if not hasattr(config.plugins.leautots, "enabled"):
	config.plugins.leautots.enabled = ConfigYesNo(default=True)
if not hasattr(config.plugins.leautots, "minminutes"):
	config.plugins.leautots.minminutes = ConfigInteger(default=10, limits=(0, 600))
if not hasattr(config.plugins.leautots, "margin"):
	config.plugins.leautots.margin = ConfigInteger(default=15, limits=(5, 300))
# Volume/mute and OSD clock are NOT handled here (use box defaults / PermanentClock).

_orig_startTimeshift = InfoBarTimeshift.startTimeshift
_orig_saveForEvent = InfoBarTimeshift.saveTimeshiftFileForEvent
_orig_saveFiles = InfoBarTimeshift.saveTimeshiftFiles
_orig_stopCb = InfoBarTimeshift.stopTimeshiftcheckTimeshiftRunningCallback
_patched = False
_clean_timer = None
_self = None  # last InfoBarTimeshift instance that was armed


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _log(msg):
	try:
		with open("/tmp/leautots.log", "a") as f:
			f.write("%s %s\n" % (strftime("%H:%M:%S"), msg))
	except Exception:
		pass
	print("[LeAutoTS]", msg)


def _cfg(name, default=None):
	try:
		return getattr(config.timeshift, name).value
	except Exception:
		return default


def _enabled():
	try:
		if not config.plugins.leautots.enabled.value:
			return False
		v = _cfg("autorecord")
		return True if v is None else v
	except Exception:
		return False


def _test_secs():
	try:
		with open("/tmp/leautots_test") as f:
			v = int(f.read().strip() or "45")
			return v if v > 0 else 0
	except Exception:
		return 0


def _min_secs():
	try:
		with open("/tmp/leautots_min") as f:
			return max(0, int(f.read().strip() or "0"))
	except Exception:
		pass
	if _test_secs():
		return 0
	try:
		return config.plugins.leautots.minminutes.value * 60
	except Exception:
		return 600


def _save_dir():
	p = _cfg("recordingPath") or ""
	if p and os.path.isdir(p):
		return p
	return defaultMoviePath()


def _event_info(self):
	name, desc, refname = "", "", ""
	try:
		info = {}
		self.getProgramInfoAndEvent(info, "")
		name = info.get("name") or ""
		ref = info.get("serviceref")
		if ref is not None:
			from ServiceReference import ServiceReference
			refname = ServiceReference(ref).getServiceName()
	except Exception:
		pass
	return refname, name, desc


# ---------------------------------------------------------------------------
# arming - called after every timeshift (re)start
# ---------------------------------------------------------------------------
def _arm(self):
	global _self
	_self = self
	self._leats_since = time()
	self._leats_pending = True
	self.save_timeshift_file = True
	self.save_timeshift_in_movie_dir = True
	self._leats_meta = _event_info(self)
	ts = self.getTimeshift()
	if ts:
		try:
			ts.saveTimeshiftFile()  # mark early: buffer survives zap/stop
		except Exception as e:
			_log("early mark error: %s" % e)
	test = _test_secs()
	if test:
		self.setCurrentEventTimer(test)
		return
	if _cfg("fileSplitting", True) is False:
		return  # continuous buffer - save only on zap/stop
	self._leats_arm_retries = 0
	_arm_event_timer(self)


def _arm_event_timer(self):
	remaining = self.currentEventTime()
	margin = config.plugins.leautots.margin.value
	if remaining > margin + 5:
		try:
			self.new_timeshift_filename = self.generateNewTimeshiftFileName()
			self._leats_meta = _event_info(self)
		except Exception:
			pass
		self.setCurrentEventTimer(remaining - margin)
	elif getattr(self, "_leats_arm_retries", 0) < 6:
		# buffer restarted right at an event boundary - wait for the EPG to
		# roll over, then arm for the NEW event
		self._leats_arm_retries = getattr(self, "_leats_arm_retries", 0) + 1
		if not getattr(self, "_leats_arm_retry", None):
			self._leats_arm_retry = eTimer()
			self._leats_arm_retry.callback.append(lambda: _delayed_arm(self))
		self._leats_arm_retry.start(25000, True)


def _delayed_arm(self):
	self._leats_arm_retry = None
	try:
		if _enabled() and getattr(self, "_leats_pending", False):
			_arm_event_timer(self)
			_log("event timer armed after rollover")
	except Exception as e:
		_log("delayed arm error: %s" % e)


def _retry_arm(self):
	self._leats_retry = None
	try:
		if _enabled() and self.timeshiftEnabled() and getattr(self, "current_timeshift_filename", None):
			_arm(self)
			_log("armed (retry)")
	except Exception as e:
		_log("retry arm error: %s" % e)


def patched_startTimeshift(self, pauseService=True):
	r = _orig_startTimeshift(self, pauseService)
	try:
		if not _enabled():
			return r
		if self.timeshiftEnabled() and getattr(self, "current_timeshift_filename", None):
			_arm(self)
			_log("armed")
		else:
			_log("arm deferred - ts not ready, retrying in 3s")
			if not getattr(self, "_leats_retry", None):
				self._leats_retry = eTimer()
				self._leats_retry.callback.append(lambda: _retry_arm(self))
			self._leats_retry.start(3000, True)
	except Exception as e:
		_log("arm error: %s" % e)
	return r


# ---------------------------------------------------------------------------
# event boundary - OpenATV "autorecord": save the finished event, start a new
# buffer for the next one
# ---------------------------------------------------------------------------
def patched_saveForEvent(self):
	if _enabled() and self.timeshiftEnabled() and getattr(self, "save_timeshift_only_current_event", False) and getattr(self, "current_timeshift_filename", None):
		watched = time() - getattr(self, "_leats_since", 0)
		self.save_timeshift_only_current_event = False
		if watched >= _min_secs():
			_log("event boundary: save+restart (watched %ds)" % watched)
			ts = self.getTimeshift()
			if ts:
				try:
					ts.saveTimeshiftFile()
				except Exception as e:
					_log("saveTimeshiftFile error: %s" % e)
			self.stopTimeshiftcheckTimeshiftRunningCallback(True)
			self.saveTimeshiftFiles()
			self.save_timeshift_file = False
			self.save_timeshift_in_movie_dir = False
			self.ts_start_delay_timer.start(1000, True)
		else:
			_log("event boundary: restart only (watched %ds)" % watched)
			self._drop_buffer()
			self.save_timeshift_file = False
			self._leats_pending = False
			self.stopTimeshiftcheckTimeshiftRunningCallback(True)
			self.ts_start_delay_timer.start(1000, True)
		return
	return _orig_saveForEvent(self)


def _drop_buffer(self):
	fn = getattr(self, "current_timeshift_filename", None)
	if not fn:
		return
	for ext in ("", ".sc", ".cuts", ".ap", ".meta"):
		try:
			os.remove(fn + ext)
		except OSError:
			pass


InfoBarTimeshift._drop_buffer = _drop_buffer


# ---------------------------------------------------------------------------
# save - wraps stock saveTimeshiftFiles; gate + meta + cleanup accounting
# ---------------------------------------------------------------------------
def patched_saveFiles(self):
	try:
		if getattr(self, "_leats_pending", False):
			watched = time() - getattr(self, "_leats_since", 0)
			if self.save_timeshift_file and watched < _min_secs():
				_log("zap/stop save skipped (watched %ds)" % watched)
				self.save_timeshift_file = False
			if not self.save_timeshift_file:
				self._drop_buffer()
			self._leats_pending = False
	except Exception as e:
		_log("saveFiles gate error: %s" % e)
	dest_base = None
	try:
		if self.save_timeshift_file:
			dirname = _save_dir() if getattr(self, "save_timeshift_in_movie_dir", True) else (config.usage.timeshift_path.value or _save_dir())
			dest_base = getRecordingFilename(self.new_timeshift_filename, dirname)
	except Exception as e:
		_log("dest base error: %s" % e)
	r = _orig_saveFiles(self)
	# user wants bare .ts only - remove moved sidecars from the destination
	if dest_base:
		for ext in (".sc", ".cuts", ".ap", ".meta", ".eit"):
			try:
				os.remove(dest_base + ext)
			except OSError:
				pass
	_schedule_sweep(_save_dir())
	return r



# sidecar sweep - engine writes .sc/.cuts asynchronously AFTER save returns;
# sweeps "*.ts.<ext>" artifacts only - live timeshift.* buffers never match
_SIDECAR_EXTS = (".sc", ".cuts", ".ap", ".eit", ".del", ".meta")
_sweep_timers = []


def _sweep_sidecars(directory):
	try:
		for fn in os.listdir(directory):
			for ext in _SIDECAR_EXTS:
				if fn.endswith(".ts" + ext):
					try:
						os.remove(os.path.join(directory, fn))
						_log("sidecar removed: %s" % fn)
					except OSError:
						pass
					break
	except Exception as e:
		_log("sidecar sweep error: %s" % e)
	try:
		mvdir = os.path.join(directory, "movie")
		if os.path.isdir(mvdir) and not os.listdir(mvdir):
			os.rmdir(mvdir)
			_log("removed empty movie/ dir")
	except Exception:
		pass


def _schedule_sweep(directory):
	def _run():
		_sweep_sidecars(directory)
	for delay in (8, 35):
		try:
			t = eTimer()
			t.callback.append(_run)
			t.start(delay * 1000, True)
			_sweep_timers.append(t)
		except Exception as e:
			_log("sweep timer error: %s" % e)
	del _sweep_timers[:-10]


def patched_stopCb(self, answer):
	r = _orig_stopCb(self, answer)
	try:
		if _enabled() and answer and getattr(self, "_leats_pending", False):
			self.saveTimeshiftFiles()
	except Exception as e:
		_log("stopCb error: %s" % e)
	return r


# ---------------------------------------------------------------------------
# cleanup daemon - port of OpenATV ptsCleanTimeshiftFolder
#   runs every checkEvents minutes on the recording dir:
#   - removes orphan timeshift.* leftovers (not the live buffer)
#   - enforces maxEvents on autosaved recordings (files with "autosaved" meta)
#   - deletes leftovers older than maxHours
# ---------------------------------------------------------------------------
def _autosaved_files(directory):
	out = []
	try:
		for fn in os.listdir(directory):
			if not fn.endswith(".ts.meta"):
				continue
			path = os.path.join(directory, fn)
			try:
				with open(path) as f:
					if "autosaved" in f.read():
						out.append(path[:-5])  # strip .meta -> .ts path
			except Exception:
				continue
	except Exception:
		pass
	return out


def _rm(path):
	for ext in ("", ".sc", ".cuts", ".ap", ".meta", ".eit", ".del"):
		try:
			os.remove(path + ext)
		except OSError:
			pass


def _mount_watchdog(directory):
	probe = os.path.join(directory, ".leats_probe")
	try:
		fd = os.open(probe, os.O_WRONLY | os.O_CREAT, 0o644)
		os.write(fd, b"x")
		os.close(fd)
		os.remove(probe)
		return  # share alive
	except Exception:
		_log("watchdog: %s not writable - remounting" % directory)
	mountpoint = dev = None
	try:
		with open("/proc/mounts") as f:
			for line in f:
				parts = line.split()
				if len(parts) < 3:
					continue
				mp = parts[1].replace("\\040", " ")
				if (directory == mp or directory.startswith(mp + "/")) and (mountpoint is None or len(mp) > len(mountpoint)):
					mountpoint, dev = mp, parts[0]
	except Exception:
		pass
	if not mountpoint or not dev or not dev.startswith("//"):
		_log("watchdog: no cifs mount found for %s" % directory)
		return
	user = passwd = ""
	try:
		import xml.etree.ElementTree as ET
		for m in ET.parse("/etc/enigma2/automounts.xml").iter("mount"):
			if (m.findtext("sharedir") or "").strip() == os.path.basename(mountpoint):
				user = m.findtext("username") or ""
				passwd = m.findtext("password") or ""
	except Exception:
		pass
	from shlex import quote
	os.system("umount -f %s 2>/dev/null; umount -l %s 2>/dev/null" % (quote(mountpoint), quote(mountpoint)))
	try:
		os.makedirs(mountpoint)
	except OSError:
		pass
	opts = "rw,nolock,sec=ntlmssp,vers=2.1,nounix,iocharset=utf8,actimeo=0"
	if user:
		opts += ",username=%s,password=%s" % (quote(user), quote(passwd))
	os.system("mount -t cifs %s %s -o %s 2>/dev/null" % (quote(dev), quote(mountpoint), opts))
	_log("watchdog: remount issued on %s" % mountpoint)
	try:
		if _self is not None and _enabled() and not _self.timeshiftEnabled():
			_self.startTimeshift()
			_log("watchdog: timeshift restarted after remount")
	except Exception as e:
		_log("watchdog: timeshift kick failed: %s" % e)


def _clean_cycle():
	global _clean_timer
	try:
		directory = _save_dir()
		try:
			_mount_watchdog(directory)
		except Exception as e:
			_log("mount watchdog error: %s" % e)
		try:
			_sweep_sidecars(directory)
		except Exception as e:
			_log("sidecar sweep error: %s" % e)
		live = getattr(_self, "current_timeshift_filename", None) if _self else None
		maxh = _cfg("maxHours", 0) or 0
		# 1) orphan timeshift leftovers (crash residue - live buffer excluded)
		try:
			live_names = set()
			if live:
				live_names = {os.path.basename(live) + ext for ext in ("", ".sc", ".cuts", ".ap", ".meta", ".eit")}
			for fn in os.listdir(directory):
				if not fn.startswith("timeshift."):
					continue
				if fn in live_names:
					continue
				path = os.path.join(directory, fn)
				try:
					age = time() - os.stat(path).st_mtime
				except OSError:
					continue
				if maxh and age < maxh * 3600:
					continue
				# never delete very young files (could belong to a running ts)
				if age < 120:
					continue
				_log("cleanup: removing orphan %s" % fn)
				try:
					os.remove(path)
				except OSError:
					pass
		except Exception as e:
			_log("cleanup orphan scan error: %s" % e)
		# 2) maxEvents on autosaved recordings - disabled: without .meta
		#    sidecars autosaved files cannot be told apart from manual ones
		maxev = 0
		if maxev > 0:
			files = _autosaved_files(directory)
			if len(files) > maxev:
				files.sort(key=lambda p: os.stat(p).st_mtime if os.path.exists(p) else 0)
				for path in files[: len(files) - maxev]:
					_log("cleanup: maxEvents remove %s" % os.path.basename(path))
					_rm(path)
	except Exception as e:
		_log("cleanup error: %s" % e)
	mins = _cfg("checkEvents", 0) or 0
	if mins > 0:
		if _clean_timer is None:
			_clean_timer = eTimer()
			_clean_timer.callback.append(_clean_cycle)
		_clean_timer.startLongTimer(mins * 60)


# ---------------------------------------------------------------------------
# Setup GUI — user-facing product name: LE Auto Record (Logic Encoder)
# ---------------------------------------------------------------------------
PLUGIN_BRAND = "Logic Encoder"
PLUGIN_URL = "https://logicencoder.com"
PLUGIN_TITLE = "LE Auto Record"
PLUGIN_ABOUT = (
	"LE Auto Record by Logic Encoder\n"
	"https://logicencoder.com\n\n"
	"OpenPLi does not save what you watch as movie files.\n"
	"This plugin does: every show you watch long enough is\n"
	"stored as a normal .ts recording on your disk or NAS.\n\n"
	"Also remounts CIFS movie folders when the NAS drops.\n"
	"For an always-on clock use PermanentClock.\n\n"
	"Author: Logic Encoder (logicencoder)\n"
	"Site: https://logicencoder.com"
)


def _path_choices():
	cands = []
	try:
		allowed = list(config.usage.allowed_timeshift_paths.value or [])
	except Exception:
		allowed = []
	for p in (
		list(allowed)
		+ [
			"/media/hdd/",
			"/media/hdd/movie/",
			"/media/net/OREC/",
			"/media/net/",
			"/media/usb/",
			"/media/usb/movie/",
		]
	):
		if not p:
			continue
		if not p.endswith("/"):
			p = p + "/"
		if p not in cands and os.path.isdir(p):
			cands.append(p)
	cur = _cfg("recordingPath") or ""
	if cur:
		if not cur.endswith("/"):
			cur = cur + "/"
		if cur not in cands:
			cands.insert(0, cur)
	if not cands:
		cands = ["/media/hdd/"]
	return [(p, p) for p in cands]


class LeAutoTimeshiftSetup(Screen, ConfigListScreen):
	skin = """
		<screen name="LeAutoTimeshiftSetup" position="center,center" size="920,620" title="LE Auto Record">
			<widget name="config" position="20,70" size="880,420" scrollbarMode="showOnDemand" />
			<widget name="brand" position="20,10" size="880,50" font="Regular;22" halign="left" valign="center" />
			<widget name="footnote" position="20,500" size="880,100" font="Regular;20" />
		</screen>
	"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_(PLUGIN_TITLE))
		self["brand"] = Label(_("%s — %s") % (PLUGIN_BRAND, PLUGIN_URL))
		self["footnote"] = Label(
			_("GREEN/OK = save   RED/EXIT = cancel   YELLOW = about\n"
			  "Saves watched TV as normal recordings. By Logic Encoder.")
		)
		choices = _path_choices()
		default_path = choices[0][0]
		try:
			cur = config.timeshift.recordingPath.value or config.usage.timeshift_path.value or default_path
		except Exception:
			cur = default_path
		if not cur.endswith("/"):
			cur = cur + "/"
		if cur not in [c[0] for c in choices]:
			choices.insert(0, (cur, cur))
		self.path_sel = ConfigSelection(default=cur, choices=choices)
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=session)
		self["actions"] = ActionMap(
			["SetupActions", "OkCancelActions", "ColorActions"],
			{
				"ok": self.keySave,
				"save": self.keySave,
				"cancel": self.keyCancel,
				"red": self.keyCancel,
				"green": self.keySave,
				"yellow": self.keyAbout,
			},
			-2,
		)
		self.onLayoutFinish.append(self._build)

	def _build(self):
		self.list = [
			getConfigListEntry(_("Enable auto-record"), config.plugins.leautots.enabled),
			getConfigListEntry(_("Save every watched programme"), config.timeshift.autorecord),
			getConfigListEntry(_("Folder for saved movies"), self.path_sel),
			getConfigListEntry(_("New file when programme changes (EPG)"), config.timeshift.fileSplitting),
			getConfigListEntry(_("Ignore zaps shorter than (minutes)"), config.plugins.leautots.minminutes),
			getConfigListEntry(_("Seconds before EPG end to rotate file"), config.plugins.leautots.margin),
			getConfigListEntry(_("Cleanup check every"), config.timeshift.checkEvents),
			getConfigListEntry(_("Keep only newest N autosaves (0 = all)"), config.timeshift.maxEvents),
			getConfigListEntry(_("Delete leftover buffers after (hours, 0 = keep)"), config.timeshift.maxHours),
			getConfigListEntry(_("Stop saving if free space below (MB, 0 = off)"), config.timeshift.checkFreeSpace),
		]
		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def keyAbout(self):
		self.session.open(MessageBox, _(PLUGIN_ABOUT), MessageBox.TYPE_INFO)

	def keySave(self):
		path = self.path_sel.value
		if not path.endswith("/"):
			path = path + "/"
		config.timeshift.recordingPath.value = path
		config.timeshift.path.value = path
		try:
			config.usage.timeshift_path.value = path
			config.usage.timeshift_path.save()
		except Exception:
			pass
		try:
			config.usage.default_path.value = path
			config.usage.default_path.save()
		except Exception:
			pass
		for entry in (
			config.plugins.leautots.enabled,
			config.plugins.leautots.minminutes,
			config.plugins.leautots.margin,
			config.timeshift.autorecord,
			config.timeshift.recordingPath,
			config.timeshift.path,
			config.timeshift.fileSplitting,
			config.timeshift.checkEvents,
			config.timeshift.maxEvents,
			config.timeshift.maxHours,
			config.timeshift.checkFreeSpace,
		):
			try:
				entry.save()
			except Exception:
				pass
		configfile.save()
		self.session.openWithCallback(
			self.close,
			MessageBox,
			_("Saved.\nWatched programmes will be stored in:\n%s\n\n%s\n%s")
			% (path, PLUGIN_BRAND, PLUGIN_URL),
			MessageBox.TYPE_INFO,
			timeout=6,
		)


def main(session, **kwargs):
	session.open(LeAutoTimeshiftSetup)


# ---------------------------------------------------------------------------
# plugin entry
# ---------------------------------------------------------------------------
def autostart(reason, **kwargs):
	global _patched
	if reason == 0 and not _patched:
		InfoBarTimeshift.startTimeshift = patched_startTimeshift
		InfoBarTimeshift.saveTimeshiftFileForEvent = patched_saveForEvent
		InfoBarTimeshift.saveTimeshiftFiles = patched_saveFiles
		InfoBarTimeshift.stopTimeshiftcheckTimeshiftRunningCallback = patched_stopCb
		_patched = True
		_clean_timer is None and _clean_cycle()
		_log("patches applied (OpenATV autorecord port)")


def Plugins(**kwargs):
	return [
		PluginDescriptor(
			name="LE Auto Record",
			description="Logic Encoder — https://logicencoder.com — auto-save watched TV as recordings on OpenPLi",
			where=PluginDescriptor.WHERE_AUTOSTART,
			fnc=autostart,
		),
		PluginDescriptor(
			name=_("LE Auto Record"),
			description=_("Logic Encoder: save watched TV as movies — https://logicencoder.com"),
			where=PluginDescriptor.WHERE_PLUGINMENU,
			fnc=main,
		),
		PluginDescriptor(
			name=_("LE Auto Record"),
			description=_("Logic Encoder: save watched TV as movies — https://logicencoder.com"),
			where=PluginDescriptor.WHERE_EXTENSIONSMENU,
			fnc=main,
		),
	]
