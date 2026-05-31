# Swift → Atari TOS

Minimal Swift "hello world" for Atari TOS / EmuTOS on m68k. Builds to `HELLO.PRG`.

![screenshot](screenshot.png)

Uses **Embedded Swift** (`-enable-experimental-feature Embedded`), so there is no
Swift runtime or stdlib to cross-build — the compiler emits a freestanding m68k
object directly. `src/main.swift` declares the GEM/GEMDOS entry points with
`@_silgen_name` and drives a `form_alert` dialog; the actual trap glue (inline
m68k assembly for the GEMDOS/AES traps) lives in `src/gemdos.c`.

Built with **Swift 6.3.2 / LLVM 21.1.6**.

Requires a `swiftc` whose bundled LLVM was built with the **M68k** backend, plus:

- a matching `clang` (same LLVM) to compile `gemdos.c` for `m68k-none-none-elf`
- m68k-elf [binutils](https://www.gnu.org/software/binutils/) (`m68k-elf-ld`)
- [toslibc](https://github.com/frno7/toslibc)'s `toslink` (creates the final `.prg`)

Build flags and the toolchain paths are in the [`Makefile`](Makefile); adjust the
`SWIFT_PREFIX` / `M68K_PREFIX` paths to your build.

```sh
make    # -> HELLO.PRG (a prebuilt copy is committed)
```

The screenshot above is from *running* `HELLO.PRG` — separate from the build. To
reproduce it, run the binary in an Atari TOS emulator such as
[Hatari](https://hatari.tuxfamily.org/) with an
[EmuTOS](https://emutos.github.io/) ROM (`hatari --tos emutos-pal.img HELLO.PRG`);
it opens a `form_alert` dialog with the version strings, then exits.
