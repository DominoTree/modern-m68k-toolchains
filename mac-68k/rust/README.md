# Rust → Classic Macintosh (System 1.0)

Cross-compile **Rust** to a runnable **classic Macintosh application** for the
original **Macintosh System 1.0** (Macintosh 128K, MC68000, 64K ROM).

The Macintosh sibling of [`atari-tos/rust`](../../atari-tos/rust), and the Rust
counterpart of [`mac-68k/swift`](../swift). Same Mac output stage (CODE-resource
packaging, MFS disk injection); the difference is the front-end and that the
Toolbox glue is inlined in Rust rather than living in a C file.

Built with **Rust nightly / LLVM 22.1.4** (whatever your nightly bundles).

![screenshot](screenshot.png)

*The `NoteAlert` under Mini vMac (an emulated Mac 128K, 64K ROM, System 1.0),
version strings supplied by Rust.*

## What it does

A modal `NoteAlert` shows three lines (`Built with: / rustc … / LLVM …`) under a
populated menu bar, then returns cleanly to the Finder via `_ExitToShell`. The
visible analogue of the Atari port's `form_alert`. Every Toolbox call
(`InitGraf` … `NoteAlert`, `ParamText`, the menu bar) is a Macintosh A-line trap
issued from inline Rust assembly, using the Pascal calling convention (caller
pushes args; the trap removes them).

## How it works

```
src/main.rs  --cargo build --release (build-std, m68k-mac.json)-->  static ELF
                                              --objcopy -O binary-->  app.bin
tools/elf2appl.py:  app.bin -> CODE 1 (code) + CODE 0 (jump table)
                            -> resource fork -> HELLO.bin (MacBinary II)
tools/inject.py:    HELLO -> a System 1.0 (MFS) disk image
```

`cargo build` does the full static link at base 0 via `app.ld` (passed as link
args in `.cargo/config.toml`), producing the flat PC-relative CODE image
directly — no separate link step.

### Position-independent code, no load-time relocation

A classic Mac `CODE` segment loads at an arbitrary address and is **not**
relocated, so all intra-segment references must be PC-relative. The custom
target (`m68k-mac.json`) sets **`"relocation-model": "pic"`** — and that detail
matters: the Swift and Zig ports get fully PC-relative m68k from the *static*
model, but rustc/LLVM emits a couple of absolute `jsr`s under `static` here
(e.g. the unreachable-after-`ExitToShell` abort path), so the Rust port needs
`pic` to push those onto PC-relative branches with no GOT. `make check-relocs`
disassembles the linked ELF and asserts no absolute `jsr`/`jmp`, no residual
relocations, and no 68020+ instructions, so the build is gated on being
68000-safe.

### No runtime byte-copy, so no scaled-index hazard

The Swift port builds its Pascal banner string at runtime, and the M68k backend
at `-Os` can pick a 68020-only scaled-index addressing mode for the copy loop
(worked around there with `optnone`). Here the banner is assembled at compile
time in a `const` block, so there is no runtime byte loop and that hazard never
arises. QuickDraw's globals buffer is the only writable `.data` (a nonzero
initializer keeps it in the loaded image, not `.bss`).

## Building

Needs the Rust nightly toolchain (`rust-src` for build-std) and the m68k
binutils (`m68k-elf-ld` on `PATH` for the cargo link step; `m68k-elf-objcopy`
/`m68k-elf-objdump` under `M68K_PREFIX`). Disk packaging also needs `python3`
with `machfs` (pip).

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
src/main.rs          Rust entry point; Toolbox trap glue inlined, comptime banner
m68k-mac.json        custom target spec (pic, code-model small, no-std)
.cargo/config.toml   build-std + static base-0 link via ../common/app.ld
build.rs             captures host rustc / LLVM versions for the banner
../common/           shared, language-agnostic Mac output stage (link script,
                     CODE-resource packaging, MFS/HFS disk writer, reloc check)
```

Committed build outputs (so you have the result without the toolchain):

```
HELLO.bin            the application as a MacBinary II file
HELLO.rsrc           the bare resource fork (what tools/inject.py writes to disk)
screenshot.png       the NoteAlert captured under Mini vMac (System 1.0)
```
