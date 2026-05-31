# Swift → Classic Macintosh (System 1.0)

Cross-compile **Swift** to a runnable **classic Macintosh application** for the
original **Macintosh System 1.0** (Macintosh 128K, MC68000, 64K ROM).

This is the Macintosh sibling of the [`atari-tos/swift`](../../atari-tos/swift)
port. It reuses the same Embedded-Swift / m68k toolchain but has its own,
self-contained Mac output stage — nothing here depends on the Atari port.

Built with **Swift 6.3.2 / LLVM 21.1.6**.

![screenshot](screenshot.png)

*The `NoteAlert` under Mini vMac (an emulated Mac 128K, 64K ROM, System 1.0),
version strings supplied by Swift. The screenshot is from running it — separate
from the build.*

## What it does

A modal `NoteAlert` shows three lines (`Built with: / Swift 6.3.2 / LLVM
21.1.6`) under a populated menu bar — the visible analogue of the Atari port's
`form_alert`. The text is provided *by Swift* (`StaticString.withUTF8Buffer` →
C → `ParamText` → the dialog's `^0` substitution; `\r` makes the line breaks),
and the Dialog Manager draws it beside the alert icon. It then returns cleanly
to the Finder via `_ExitToShell` (no system-error "bomb").

## How it works

```
src/main.swift   --swiftc (Embedded, m68k)-->  main.o     \
src/mactraps.c   --clang (-fpic, m68k)----->  mactraps.o   |  full static link,
                                                           |  base 0 (m68k-elf-ld)
                              app.ld  -------------------->  app.elf
                                              --objcopy -O binary-->  app.bin
tools/elf2appl.py:  app.bin -> CODE 1 (code) + CODE 0 (jump table)
                            -> resource fork -> HELLO.bin (MacBinary II)
tools/inject.py:    HELLO -> a System 1.0 (MFS) or HFS disk image
```

### Position-independent code, no load-time relocation

A classic Mac `CODE` segment is loaded at an arbitrary address and is **not**
relocated (unlike a GEMDOS `.PRG`, which carries a relocation table), so all
intra-segment references must be PC-relative:

- Swift built with `-Xllvm -relocation-model=static` emits fully PC-relative
  m68k code (`jsr %pc@(...)`, `lea %pc@(...)`, PC-relative data loads).
- The C glue **must** use `-fpic` (not `-fno-pic`) — otherwise clang emits
  absolute `jsr` (`4eb9`). With `-fpic` the calls become `R_68K_PLT16`, which
  the full static link resolves to direct PC-relative branches.

`make check-relocs` disassembles `app.elf` and asserts there are no absolute
`jsr`/`jmp`, no residual relocations, and no 68020+ instructions, so the build
is gated on being 68000-safe.

### OPNOTE — M68k toolchain gotchas (LLVM 21 m68k is young)

Three real limitations bit us; all are worked around in-tree:

1. **Scaled-index addressing on the 68000.** At `-Os` the M68k backend can emit
   a `move.b (d8,An,Xn*2)` scaled-index mode — a 68020+ feature — for byte-copy
   loops, even with `-mcpu=M68000`. On a 68000 it faults as an illegal
   instruction. Workaround: the byte-loop functions (`show_version_alert`,
   `memset/memcpy/memmove`) are marked `__attribute__((optnone))`, whose `-O0`
   codegen only uses simple register-indirect addressing. `check-relocs` catches
   any regression.
2. **Immature integrated assembler.** LLVM's m68k IAS rejects common mnemonics
   (`tst.w`, `subq.w`, `cmp.w`, `dbra`, …), so the loop can't simply be
   hand-written in inline asm — hence the `optnone` approach above.
3. **`&staticString` came out ~15 bytes off** in testing — so hand the bytes
   over with `StaticString.withUTF8Buffer { … }` (what `main.swift` does) rather
   than taking the static string's address. The exact cause wasn't bisected
   here: the Atari port saw a similar symptom from a real linker / `toslink`
   section gap, but this pipeline is a single contiguous section (`app.ld`) with
   no relocation step, so that mechanism shouldn't apply. `withUTF8Buffer` is a
   robust workaround regardless.

### CODE-resource layout (`tools/elf2appl.py`)

- **CODE 0** (24 bytes): jump-table header `above-A5=40, below-A5=0, JT len=8,
  JT off=32` + one unloaded entry `0000 3F3C 0001 A9F0` (routine offset 0,
  `MOVE.W #1,-(SP)`, `_LoadSeg`).
- **CODE 1**: 4-byte segment header `0000 0001` + the flat PC-relative code;
  `_start` is at code offset 0. Because our code needs no relocation, we drop it
  in raw — simpler than Retro68's flow, which needs a load-time relocator.

Layout cross-checked against Inside Macintosh (Processes / Runtime) and
Retro68's `Elf2Mac` `SingleSegmentApp`.

## Building

Same Embedded-Swift / m68k toolchain as the other ports (an LLVM built with the
experimental **M68k** backend). The `Makefile` has `SWIFT_PREFIX` and
`M68K_PREFIX` at the top pointing at local build paths — edit those to match
where you built yours. Disk packaging also needs `python3` with `machfs` (pip).

```sh
make               # -> HELLO.bin (MacBinary II application) + HELLO.rsrc
make check-relocs  # confirm PC-relative / relocation-free / 68000-only
```

This is a GNU-make Makefile, so use `gmake` on platforms where `make` is BSD
make.

> **System 1.0 disks are MFS, not HFS** (HFS arrived in 1986). The common HFS
> libraries can't write them, so `tools/mfs.py` is a minimal MFS reader/writer.
> `tools/inject.py` auto-detects the volume's filesystem and uses the right one.

## Packaging onto a disk

`make disk SYSDISK="path/to/system-1.0.img"` adds HELLO to a copy of a System
1.0 disk image (you supply the copyrighted ROM and disk). Boot the resulting
`build/boot.dsk` in a Mac 128K emulator (e.g. Mini vMac) to see it run.

## Files

```
src/main.swift       Swift entry point (Embedded); hands the banner to C
src/mactraps.c       Toolbox trap glue + QuickDraw init + 68000-safe shims
../common/           shared, language-agnostic Mac output stage (link script,
                     CODE-resource packaging, MFS/HFS disk writer, reloc check)
```

Committed build outputs (so you have the result without the toolchain):

```
HELLO.bin            the application as a MacBinary II file (for distribution)
HELLO.rsrc           the bare resource fork (what tools/inject.py writes to disk)
screenshot.png       the NoteAlert captured under Mini vMac (System 1.0)
```

`HELLO.rsrc` is the same resource fork carried inside `HELLO.bin`, split out
because `inject.py` writes the fork directly onto a disk image; keeping it
committed lets you build a runnable disk straight from the prebuilt files.
