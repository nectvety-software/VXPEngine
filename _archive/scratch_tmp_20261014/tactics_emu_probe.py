"""Is the live TacticsVanguard2D app hung or merely idle-drawing? Grab, send
keys, grab again and byte-compare against a DIB hash instead of PIL diff."""
import ctypes, hashlib, time
import tactics_emu_probe_lib as L
