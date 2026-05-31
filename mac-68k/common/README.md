# mac-68k/common — shared Mac output stage

The classic-Mac output stage is **language-agnostic**: it turns a linked m68k
ELF into a runnable System 1.0 application and drops it on a disk. The Rust,
Swift, and Zig Mac ports differ only in the front-end (how the `.o` is produced);
everything from the link script onward is identical, so it lives here once
instead of being copied into each port.

```
app.ld             flat base-0, PC-relative link script for a single CODE segment
check-relocs.mk    make-include: assert the linked image is relocation-free 68000-only
tools/elf2appl.py  app.bin -> CODE 0 (jump table) + CODE 1 (code) -> MacBinary II
tools/inject.py    write the app's resource fork into an MFS or HFS disk image
tools/mfs.py       minimal MFS (Macintosh File System) reader/writer
```

Each port's `Makefile` sets `COMMON := ../common`, links with
`--script=$(COMMON)/app.ld`, runs `python3 $(COMMON)/tools/elf2appl.py …`, and
`include $(COMMON)/check-relocs.mk`. `check-relocs.mk` expects the including
Makefile to define `OBJDUMP`, `ELF`, and `RELOC_DEP` (the prerequisite that
builds `$(ELF)` — the ELF file for swift/zig, or a phony `elf` cargo target for
rust).

Nothing here is Mac-port-specific or language-specific; it is the counterpart of
the Atari ports' `toslink` step (which, being a prebuilt binary, needs no shared
source).
