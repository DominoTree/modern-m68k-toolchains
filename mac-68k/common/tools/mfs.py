#!/usr/bin/env python3
"""Minimal MFS (Macintosh File System) reader + injector.

The original Macintosh System 1.0 uses MFS, not HFS (HFS arrived in 1986). So
machfs / hfsutils cannot write to a real System 1.0 floppy. This adds a file
(with a resource fork) to a copy of an MFS volume — enough to drop our Swift
app onto a bootable System 1.0 disk.

MFS layout (logical blocks of 512 bytes):
  blocks 0-1  : boot blocks
  block  2 +  : Master Directory Block (64-byte volume info, then the 12-bit
                Volume Allocation Block Map)
  drDirSt +   : file directory (fixed-size-field entries + Pascal name, even
                aligned, never crossing a 512-byte block boundary)
  drAlBlSt +  : allocation blocks (the fork data)

Allocation map: one 12-bit entry per allocation block, packed big-endian.
0 = free, 1 = last block of a file (EOF), >=2 = next allocation block number.
Allocation block numbers are 2-based; map index i <-> allocation block i+2.

References: Inside Macintosh vol II (File Manager / MFS); validated against a
real System 1.0 disk (known file fork lengths match their decoded chains).
"""
import argparse
import struct
import sys
import time

MAC_EPOCH_DELTA = 2082844800
BLOCK = 512
MDB_OFF = 2 * BLOCK            # MDB at logical block 2
MAP_OFF = MDB_OFF + 64         # map follows the 64-byte volume info


class MFS:
    def __init__(self, image: bytes):
        self.d = bytearray(image)
        m = self.d[MDB_OFF:]
        (self.sig,) = struct.unpack(">H", m[0:2])
        if self.sig != 0xD2D7:
            raise ValueError(f"not an MFS volume (sig {self.sig:04X})")
        (self.nFiles,) = struct.unpack(">H", m[12:14])
        (self.dirSt,) = struct.unpack(">H", m[14:16])
        (self.dirLen,) = struct.unpack(">H", m[16:18])
        (self.nAlBlks,) = struct.unpack(">H", m[18:20])
        (self.alBlkSiz,) = struct.unpack(">I", m[20:24])
        (self.alBlSt,) = struct.unpack(">H", m[28:30])
        (self.nxtFNum,) = struct.unpack(">I", m[30:34])
        (self.freeBks,) = struct.unpack(">H", m[34:36])
        self.volName = m[37:37 + m[36]].decode("mac-roman")

    # --- allocation map ---
    def get_alloc(self, i: int) -> int:
        base = MAP_OFF + (i // 2) * 3
        b0, b1, b2 = self.d[base], self.d[base + 1], self.d[base + 2]
        return (b0 << 4) | (b1 >> 4) if i % 2 == 0 else ((b1 & 0xF) << 8) | b2

    def set_alloc(self, i: int, val: int) -> None:
        base = MAP_OFF + (i // 2) * 3
        if i % 2 == 0:
            self.d[base] = (val >> 4) & 0xFF
            self.d[base + 1] = ((val & 0xF) << 4) | (self.d[base + 1] & 0x0F)
        else:
            self.d[base + 1] = (self.d[base + 1] & 0xF0) | ((val >> 8) & 0xF)
            self.d[base + 2] = val & 0xFF

    def free_blocks(self):
        return [i + 2 for i in range(self.nAlBlks) if self.get_alloc(i) == 0]

    def alloc_block_offset(self, blknum: int) -> int:
        """File byte offset of 2-based allocation block number."""
        logical = self.alBlSt + (blknum - 2) * (self.alBlkSiz // BLOCK)
        return logical * BLOCK

    # --- directory ---
    def iter_dir(self):
        """Yield (logical_block, offset_in_block, entry_len, name) for each
        in-use directory entry."""
        for blk in range(self.dirSt, self.dirSt + self.dirLen):
            base = blk * BLOCK
            pos = 0
            while pos < BLOCK:
                flags = self.d[base + pos]
                if flags & 0x80 == 0:
                    break  # no more entries in this block
                namelen = self.d[base + pos + 50]
                ent = 51 + namelen
                if ent % 2:
                    ent += 1
                name = self.d[base + pos + 51:base + pos + 51 + namelen].decode("mac-roman", "replace")
                yield blk, pos, ent, name
                pos += ent

    def list_files(self):
        for blk, off, ent, name in self.iter_dir():
            b = blk * BLOCK + off
            typ = bytes(self.d[b + 2:b + 6])
            creator = bytes(self.d[b + 6:b + 10])
            (rstart,) = struct.unpack(">H", self.d[b + 32:b + 34])
            (rlen,) = struct.unpack(">I", self.d[b + 34:b + 38])
            print(f"  {name!r:24} {typ!r}/{creator!r} rsrcBlk={rstart} rsrcLen={rlen}")

    def find_append_slot(self, entry_len: int):
        """Return (logical_block, offset) where an entry of entry_len fits
        without crossing a block boundary."""
        used = {}  # block -> bytes used
        for blk, off, ent, _ in self.iter_dir():
            used[blk] = off + ent
        for blk in range(self.dirSt, self.dirSt + self.dirLen):
            u = used.get(blk, 0)
            if u + entry_len <= BLOCK:
                return blk, u
        raise RuntimeError("no room in file directory")

    # --- injection ---
    def add_file(self, name: str, ftype: bytes, creator: bytes, rsrc: bytes):
        nblocks = (len(rsrc) + self.alBlkSiz - 1) // self.alBlkSiz
        free = self.free_blocks()
        if len(free) < nblocks:
            raise RuntimeError(f"need {nblocks} blocks, only {len(free)} free")
        chain = free[:nblocks]

        # write fork data
        for k, blknum in enumerate(chain):
            off = self.alloc_block_offset(blknum)
            seg = rsrc[k * self.alBlkSiz:(k + 1) * self.alBlkSiz]
            self.d[off:off + len(seg)] = seg
            # zero the remainder of the final allocation block
            if len(seg) < self.alBlkSiz:
                self.d[off + len(seg):off + self.alBlkSiz] = b"\x00" * (self.alBlkSiz - len(seg))
        # link the allocation chain (each -> next, last = EOF)
        for k, blknum in enumerate(chain):
            nxt = chain[k + 1] if k + 1 < len(chain) else 1
            self.set_alloc(blknum - 2, nxt)

        # build the directory entry
        nb = name.encode("mac-roman")
        ent_len = 51 + len(nb)
        if ent_len % 2:
            ent_len += 1
        e = bytearray(ent_len)
        e[0] = 0x80                                   # flFlags: in use
        e[1] = 0                                      # flTyp / version
        e[2:6] = ftype                                # FInfo: type
        e[6:10] = creator                             #        creator
        # e[10:18] FInfo flags/location/folder = 0
        struct.pack_into(">I", e, 18, self.nxtFNum)   # flFlNum
        struct.pack_into(">H", e, 22, 0)              # flStBlk (no data fork)
        struct.pack_into(">I", e, 24, 0)              # flLgLen
        struct.pack_into(">I", e, 28, 0)              # flPyLen
        struct.pack_into(">H", e, 32, chain[0])       # flRStBlk
        struct.pack_into(">I", e, 34, len(rsrc))      # flRLgLen
        struct.pack_into(">I", e, 38, nblocks * self.alBlkSiz)  # flRPyLen
        now = int(time.time()) + MAC_EPOCH_DELTA
        struct.pack_into(">I", e, 42, now)            # flCrDat
        struct.pack_into(">I", e, 46, now)            # flMdDat
        e[50] = len(nb)
        e[51:51 + len(nb)] = nb

        blk, off = self.find_append_slot(ent_len)
        base = blk * BLOCK + off
        self.d[base:base + ent_len] = e

        # update the MDB
        m = MDB_OFF
        self.nFiles += 1
        self.nxtFNum += 1
        self.freeBks -= nblocks
        struct.pack_into(">H", self.d, m + 12, self.nFiles)
        struct.pack_into(">I", self.d, m + 30, self.nxtFNum)
        struct.pack_into(">H", self.d, m + 34, self.freeBks)

    def bytes(self) -> bytes:
        return bytes(self.d)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", help="MFS disk image")
    ap.add_argument("--list", action="store_true", help="list files and exit")
    ap.add_argument("--add-rsrc", help="raw resource fork to inject (elf2appl --rsrc-out)")
    ap.add_argument("--name", default="HELLO")
    ap.add_argument("--type", default="APPL")
    ap.add_argument("--creator", default="SWFT")
    ap.add_argument("--out", help="output image (required with --add-rsrc)")
    args = ap.parse_args()

    fs = MFS(open(args.image, "rb").read())
    print(f"MFS volume {fs.volName!r}: {fs.nFiles} files, {fs.freeBks} free "
          f"{fs.alBlkSiz}-byte blocks ({fs.freeBks * fs.alBlkSiz} bytes)")
    if args.list or not args.add_rsrc:
        fs.list_files()
        return 0

    if not args.out:
        ap.error("--out is required with --add-rsrc")
    rsrc = open(args.add_rsrc, "rb").read()
    fs.add_file(args.name, args.type.encode("mac-roman"),
                args.creator.encode("mac-roman"), rsrc)
    open(args.out, "wb").write(fs.bytes())
    print(f"added {args.name!r} ({args.type}/{args.creator}, rsrc {len(rsrc)}B) -> {args.out}")
    print("now contains:")
    MFS(open(args.out, "rb").read()).list_files()
    return 0


if __name__ == "__main__":
    sys.exit(main())
