#!/usr/bin/env python3
"""Inject the packaged app onto a Mac disk image, preserving its resource fork.

Auto-detects the filesystem of --base and dispatches:
  * MFS (System 1.0, sig D2D7) -> tools/mfs.py (our own minimal MFS writer);
    machfs/hfsutils cannot write MFS.
  * HFS (sig 'BD')             -> machfs (handles 400K, unlike hfsutils).

Modes:
  * --base SYSTEM.dsk : copy an existing (bootable) disk image and add the app.
                        Use this to drop HELLO onto a System 1.0 floppy.
  * (no --base)       : create a fresh, non-bootable HFS volume with just the app.

The app's resource fork comes from elf2appl.py's --rsrc-out.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def inject_mfs(base, out, name, ftype, creator, rsrc):
    from mfs import MFS
    fs = MFS(open(base, "rb").read())
    fs.add_file(name, ftype.encode("mac-roman"), creator.encode("mac-roman"), rsrc)
    open(out, "wb").write(fs.bytes())
    print(f"wrote {out}: {name} ({ftype}/{creator}, rsrc {len(rsrc)}B) — added to MFS copy of {base}")


def inject_hfs(base, out, name, ftype, creator, rsrc, size, volname):
    from machfs import Volume, File
    v = Volume()
    if base:
        v.read(open(base, "rb").read())
        sz = None
    else:
        v.name = volname
        sz = size * 1024
    f = File()
    f.type, f.creator, f.data, f.rsrc = ftype.encode("mac-roman"), creator.encode("mac-roman"), b"", rsrc
    v[name] = f
    img = v.write(sz, desktopdb=False, bootable=False) if sz else v.write()
    open(out, "wb").write(img)
    where = f"added to HFS copy of {base}" if base else f"new {size}K HFS volume {volname!r}"
    print(f"wrote {out}: {name} ({ftype}/{creator}, rsrc {len(rsrc)}B) — {where}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rsrc", required=True, help="raw resource fork (elf2appl --rsrc-out)")
    ap.add_argument("--out", required=True, help="output disk image (.dsk)")
    ap.add_argument("--base", help="existing disk image (MFS or HFS) to copy and add the app to")
    ap.add_argument("--name", default="HELLO")
    ap.add_argument("--type", default="APPL")
    ap.add_argument("--creator", default="SWFT")
    ap.add_argument("--size", type=int, default=400, help="new-volume size in KB (no --base)")
    ap.add_argument("--volname", default="Swift", help="new-volume name (no --base)")
    args = ap.parse_args()

    rsrc = open(args.rsrc, "rb").read()

    if args.base:
        sig = open(args.base, "rb").read(1026)[1024:1026]
        if sig == bytes([0xD2, 0xD7]):
            inject_mfs(args.base, args.out, args.name, args.type, args.creator, rsrc)
            return 0
        if sig != b"BD":
            print(f"warning: unrecognized volume signature {sig.hex()}; trying HFS", file=sys.stderr)
    inject_hfs(args.base, args.out, args.name, args.type, args.creator, rsrc, args.size, args.volname)
    return 0


if __name__ == "__main__":
    sys.exit(main())
