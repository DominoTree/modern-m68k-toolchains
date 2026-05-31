# Zig → Atari TOS

Minimal Zig "hello world" for Atari TOS / EmuTOS on m68k. Builds to `HELLO.PRG`.

![screenshot](screenshot.png)

Compiled `freestanding` with no standard library — every system call is inline
m68k assembly. `src/main.zig` builds an AES parameter block on the stack and
issues the GEMDOS (`trap #1`) and AES (`trap #2`) traps directly to drive a GEM
`form_alert` dialog, then exits via `Pterm0`. `src/build_info.zig` is generated
at build time from `llvm-config --version` to stamp the LLVM version into the
dialog.

Built with a custom Zig build over **LLVM 21.1.8**.

Requires a `zig` whose LLVM was built with the **M68k** backend, plus:

- m68k-elf [binutils](https://www.gnu.org/software/binutils/) (`m68k-elf-ld`)
- [toslibc](https://github.com/frno7/toslibc)'s `toslink` (creates the final `.prg`)

Build flags and the toolchain paths are in the [`Makefile`](Makefile); adjust the
`M68K_PREFIX` path to your build.

```sh
make    # -> HELLO.PRG (a prebuilt copy is committed)
```

The screenshot above is from *running* `HELLO.PRG` — separate from the build. To
reproduce it, run the binary in an Atari TOS emulator such as
[Hatari](https://hatari.tuxfamily.org/) with an
[EmuTOS](https://emutos.github.io/) ROM (`hatari --tos emutos-pal.img HELLO.PRG`);
it opens a `form_alert` dialog with the version strings, then exits.
