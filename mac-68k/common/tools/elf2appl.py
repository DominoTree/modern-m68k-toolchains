#!/usr/bin/env python3
"""Package a flat, relocation-free m68k code blob into a classic Macintosh
application (resource fork with CODE 0 + CODE 1), wrapped in MacBinary II.

This is the Mac equivalent of toslibc's `toslink` (which makes a GEMDOS .PRG).
It is a host-side build tool only; nothing here ships to the Mac.

Why this is simpler than Retro68's Elf2Mac: our Swift+clang output is compiled
fully PC-relative (verified: no absolute jsr, zero residual relocations), so the
CODE segment runs correctly at whatever address the Segment Loader places it at,
with no load-time relocation runtime. We just drop the raw code into CODE 1.

Layout references (cross-checked):
  * CODE 0 / jump table  - Inside Macintosh: Processes "The Jump Table";
    Retro68 Elf2Mac SingleSegmentApp (the literal 00000028/0008/0020 + the
    0000 3F3C 0001 A9F0 unloaded jump-table entry).
  * CODE 1 4-byte header - two words: first-JT-entry offset (0) and entry
    count (1), then the code; routine offset 0 = "0 bytes past the header".
  * Resource fork format - Inside Macintosh: More Macintosh Toolbox,
    Resource Manager "Resource File Format".
  * MacBinary II header  - the MacBinary II standard (128-byte header, CRC-16
    CCITT/XMODEM over bytes 0..123).
"""

import argparse
import struct
import sys
import time

# Seconds between the HFS epoch (1904-01-01) and the Unix epoch (1970-01-01).
MAC_EPOCH_DELTA = 2082844800


# --- CODE resources ---------------------------------------------------------

def build_code0() -> bytes:
    """The 24-byte CODE 0 jump-table segment for a single-segment app."""
    return bytes.fromhex(
        "00000028"   # size above A5 = 40 (32 app-parameter bytes + 8 jump table)
        "00000000"   # size below A5 = 0  (no application globals)
        "00000008"   # jump table length = 8 (one entry)
        "00000020"   # jump table offset from A5 = 32
        # one unloaded jump table entry:
        "0000"       #   routine offset within segment = 0 (after the 4-byte hdr)
        "3F3C"       #   MOVE.W #segID,-(SP)
        "0001"       #   segID = 1  (the CODE 1 resource)
        "A9F0"       #   _LoadSeg trap
    )


def build_code1(code: bytes) -> bytes:
    """CODE 1 = 4-byte segment header + the flat PC-relative code blob."""
    if len(code) % 2:
        code += b"\x00"                     # keep word alignment
    header = struct.pack(">HH", 0, 1)       # first JT-entry offset 0, 1 entry
    return header + code


# --- Dialog resources (Milestone 2) -----------------------------------------

def build_alrt() -> bytes:
    """ALRT 128: boundsRect, DITL id 128, stages word $4444 (visible at every
    stage, default = item 1, silent). Centered ~360x110 on the 512x342 screen."""
    return bytes.fromhex(
        "0074 004C 00E2 01B4"   # boundsRect {116,76,226,436}
        "0080"                  # itemsID -> DITL 128
        "4444"                  # stages: drawn, item-1 default, no beep
    )


def _ditl_item(rect_hex: str, itype: int, data: bytes) -> bytes:
    body = struct.pack(">I", 0)                       # placeholder handle
    body += bytes.fromhex(rect_hex)                   # display rect (4 INTEGERs)
    body += bytes([itype, len(data)]) + data          # type, length, data
    if len(body) % 2:
        body += b"\x00"
    return body


def build_ditl() -> bytes:
    """DITL 128: item 1 = enabled Button 'OK' (the default), item 2 = StaticText
    '^0' (replaced at draw time by the ParamText string the Swift code sets)."""
    # Layout within the 360x110 alert: note icon is auto-drawn top-left
    # (~{10,20,42,52}); text sits to its right; OK button bottom-right. Keep the
    # text rect clear of the icon (left=70) AND well above the button's bold
    # default-outline ring (text bottom 68 vs button at top 80) so drawing the
    # text doesn't erase the button.
    items = [
        _ditl_item("0050 0118 0064 0154", 0x04, b"OK"),   # button {80,280,100,340}
        _ditl_item("0006 0046 0044 015E", 0x88, b"^0"),   # static text {6,70,68,350}, 3 lines
    ]
    out = struct.pack(">H", len(items) - 1)
    for it in items:
        out += it
    return out


# --- Resource fork ----------------------------------------------------------

DATA_AREA_START = 256   # conventional: first 256 bytes reserved for system use

def build_resource_fork(resources) -> bytes:
    """resources: list of (type4, id, payload). Returns the raw resource fork.

    Resource fork = header(16) + data + map. Data: each resource is a 4-byte
    big-endian length followed by its bytes. Map: reserved(16) + reserved
    next/refnum/attrs(8) + type-list-offset(2) + name-list-offset(2) + type
    list + reference lists + name list (empty here)."""
    # Resource data section, recording each resource's offset within it.
    data = bytearray()
    data_offsets = {}
    for typ, rid, payload in resources:
        data_offsets[(typ, rid)] = len(data)
        data += struct.pack(">I", len(payload))
        data += payload

    # Group resources by type, preserving first-seen order.
    types = []
    by_type = {}
    for typ, rid, payload in resources:
        if typ not in by_type:
            by_type[typ] = []
            types.append(typ)
        by_type[typ].append(rid)

    # Map header is 28 bytes; the type list begins right after it.
    TYPE_LIST_OFFSET = 28
    type_list_count = len(types)
    # type list = 2-byte (count-1) + 8 bytes per type
    type_list_size = 2 + 8 * type_list_count
    # reference lists follow the type list, in type order
    ref_list = bytearray()
    type_entries = bytearray()
    type_entries += struct.pack(">H", type_list_count - 1)
    for typ in types:
        ids = by_type[typ]
        ref_off = type_list_size + len(ref_list)   # from start of type list
        type_entries += typ.encode("mac-roman")
        type_entries += struct.pack(">HH", len(ids) - 1, ref_off)
        for rid in ids:
            doff = data_offsets[(typ, rid)]
            ref_list += struct.pack(">H", rid & 0xFFFF)   # resource ID
            ref_list += struct.pack(">H", 0xFFFF)         # no name
            ref_list += bytes([0])                        # attributes
            ref_list += doff.to_bytes(3, "big")           # 3-byte data offset
            ref_list += struct.pack(">I", 0)              # reserved handle

    name_list_offset = TYPE_LIST_OFFSET + len(type_entries) + len(ref_list)
    res_map = bytearray()
    res_map += b"\x00" * 16                               # reserved (hdr copy)
    res_map += struct.pack(">I", 0)                       # reserved next map
    res_map += struct.pack(">H", 0)                       # reserved file refnum
    res_map += struct.pack(">H", 0)                       # fork attributes
    res_map += struct.pack(">H", TYPE_LIST_OFFSET)        # -> type list
    res_map += struct.pack(">H", name_list_offset)        # -> name list
    res_map += type_entries
    res_map += ref_list
    # name list is empty

    data_offset = DATA_AREA_START
    map_offset = data_offset + len(data)
    header = struct.pack(">IIII", data_offset, map_offset, len(data), len(res_map))

    fork = bytearray()
    fork += header
    fork += b"\x00" * (data_offset - len(header))         # system-reserved gap
    fork += data
    fork += res_map
    return bytes(fork)


# --- MacBinary II -----------------------------------------------------------

def _crc16_ccitt(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


def _pad128(data: bytes) -> bytes:
    rem = len(data) % 128
    return data + b"\x00" * ((128 - rem) % 128)


def build_macbinary(name: str, ftype: str, creator: str,
                    data_fork: bytes, rsrc_fork: bytes) -> bytes:
    name_b = name.encode("mac-roman")[:63]
    h = bytearray(128)
    h[0] = 0                                              # old version, must be 0
    h[1] = len(name_b)                                    # filename length
    h[2:2 + len(name_b)] = name_b                         # filename
    h[65:69] = ftype.encode("mac-roman")                  # file type
    h[69:73] = creator.encode("mac-roman")                # file creator
    h[73] = 0                                             # Finder flags (high)
    h[74] = 0                                             # must be 0
    struct.pack_into(">I", h, 83, len(data_fork))         # data fork length
    struct.pack_into(">I", h, 87, len(rsrc_fork))         # resource fork length
    mac_now = int(time.time()) + MAC_EPOCH_DELTA
    struct.pack_into(">I", h, 91, mac_now)                # creation date
    struct.pack_into(">I", h, 95, mac_now)                # modification date
    h[101] = 0                                            # Finder flags (low)
    h[122] = 129                                          # written by MacBinary II
    h[123] = 129                                          # min version to read
    struct.pack_into(">H", h, 124, _crc16_ccitt(bytes(h[0:124])))
    return bytes(h) + _pad128(data_fork) + _pad128(rsrc_fork)


# --- driver -----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bin", required=True, help="flat m68k code blob (objcopy -O binary)")
    ap.add_argument("--out", required=True, help="output MacBinary II file")
    ap.add_argument("--elf", help="(optional) linked ELF, for diagnostics")
    ap.add_argument("--name", default="HELLO", help="Mac file name")
    ap.add_argument("--type", default="APPL", help="4-char file type")
    ap.add_argument("--creator", default="SWFT", help="4-char file creator")
    ap.add_argument("--rsrc-out", help="(optional) also write the raw resource fork")
    ap.add_argument("--dialog", action="store_true",
                    help="include ALRT/DITL 128 resources for the NoteAlert demo")
    args = ap.parse_args()

    with open(args.bin, "rb") as f:
        code = f.read()

    code0 = build_code0()
    code1 = build_code1(code)
    resources = [("CODE", 0, code0), ("CODE", 1, code1)]
    if args.dialog:
        resources += [("ALRT", 128, build_alrt()), ("DITL", 128, build_ditl())]
    fork = build_resource_fork(resources)
    if args.rsrc_out:
        with open(args.rsrc_out, "wb") as f:
            f.write(fork)

    mb = build_macbinary(args.name, args.type, args.creator, b"", fork)
    with open(args.out, "wb") as f:
        f.write(mb)

    print(f"code blob   : {len(code)} bytes")
    print(f"CODE 0      : {len(code0)} bytes")
    print(f"CODE 1      : {len(code1)} bytes (4-byte seg header + code)")
    print(f"resource fork: {len(fork)} bytes")
    print(f"wrote {args.out} ({len(mb)} bytes, type '{args.type}' creator '{args.creator}')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
