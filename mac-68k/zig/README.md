# Zig → Classic Macintosh (System 1.0)

Cross-compile **Zig** to a runnable **classic Macintosh application** for the
original **Macintosh System 1.0** (Macintosh 128K, MC68000, 64K ROM).

The Macintosh sibling of [`atari-tos/zig`](../../atari-tos/zig), and the Zig
counterpart of [`mac-68k/swift`](../swift). Same Mac output stage (CODE-resource
packaging, MFS disk injection); the difference is the front-end and that the
Toolbox glue is inlined in Zig rather than living in a C file.

Built with **Zig 0.16.0-dev / LLVM 21.1.8**.

![screenshot](screenshot.png)

*The `NoteAlert` under Mini vMac (an emulated Mac 128K, 64K ROM, System 1.0),
version strings supplied by Zig.*

## What it does

A modal `NoteAlert` shows three lines (`Built with: / zig … / LLVM …`) under a
populated menu bar, then returns cleanly to the Finder via `_ExitToShell`. The
visible analogue of the Atari port's `form_alert`. Every Toolbox call
(`InitGraf` … `NoteAlert`, `ParamText`, the menu bar) is a Macintosh A-line trap
issued from inline Zig assembly, using the Pascal calling convention (caller
pushes args; the trap removes them).

## How it works

```
src/main.zig  --zig build-obj (ReleaseSmall, m68k)-->  main.o   (PC-relative)
                              app.ld  --m68k-elf-ld (static, base 0)-->  app.elf
                                              --objcopy -O binary-->  app.bin
tools/elf2appl.py:  app.bin -> CODE 1 (code) + CODE 0 (jump table)
                            -> resource fork -> HELLO.bin (MacBinary II)
tools/inject.py:    HELLO -> a System 1.0 (MFS) disk image
```

### Position-independent code, no load-time relocation

A classic Mac `CODE` segment loads at an arbitrary address and is **not**
relocated, so all intra-segment references must be PC-relative. Zig's default
freestanding m68k codegen already emits PC-relative control flow and data loads
(`jsr %pc@(…)`, `lea %pc@(…)`) with no absolute `R_68K_32` — no special flag is
needed. `make check-relocs` disassembles `app.elf` and asserts there are no
absolute `jsr`/`jmp`, no residual relocations, and no 68020+ instructions, so the
build is gated on being 68000-safe.

### No runtime byte-copy, so no scaled-index hazard

The Swift port builds its Pascal banner string at runtime, and the M68k backend
at `-Os` can pick a 68020-only scaled-index addressing mode for the copy loop
(worked around there with `optnone`). Here the banner is a compile-time
constant, so the `Str255` (length byte + bytes) is assembled at **comptime** —
there is no runtime byte loop, so that hazard never arises. QuickDraw's globals
buffer is the only writable `.data` (forced non-zero so it lands in the loaded
image, not `.bss`).

## Building

Same m68k toolchain as the other ports (an LLVM built with the experimental
**M68k** backend, plus the Zig that targets it). `M68K_PREFIX` at the top of the
`Makefile` points at the local build path — edit it to match yours. Disk
packaging also needs `python3` with `machfs` (pip).

```sh
make               # -> HELLO.bin (MacBinary II application) + HELLO.rsrc
make check-relocs  # confirm PC-relative / relocation-free / 68000-only
```

GNU-make Makefile — use `gmake` where `make` is BSD make.

## Packaging onto a disk

`make disk SYSDISK="path/to/system-1.0.img"` adds HELLO to a copy of a System
1.0 disk image (you supply the copyrighted ROM and disk). Boot the resulting
`build/boot.dsk` in a Mac 128K emulator (e.g. Mini vMac) to see it run.

## Files

```
src/main.zig         Zig entry point; Toolbox trap glue inlined, comptime banner
../common/           shared, language-agnostic Mac output stage (link script,
                     CODE-resource packaging, MFS/HFS disk writer, reloc check)
```

Committed build outputs (so you have the result without the toolchain):

```
HELLO.bin            the application as a MacBinary II file
HELLO.rsrc           the bare resource fork (what tools/inject.py writes to disk)
screenshot.png       the NoteAlert captured under Mini vMac (System 1.0)
```
