# RuST

Minimal Rust "hello world" for Atari TOS / EmuTOS on m68k. Builds to `HELLO.PRG`.

![screenshot](screenshot.png)

Requires on `PATH`:

- Rust nightly with `rust-src` (pinned in `rust-toolchain.toml`)
- m68k-elf [binutils](https://www.gnu.org/software/binutils/) (`m68k-elf-ld`)
- [toslibc](https://github.com/frno7/toslibc)'s `toslink` (creates the final `.prg`)

```sh
make    # -> HELLO.PRG (a prebuilt copy is committed)
```

The screenshot above is from *running* `HELLO.PRG` — separate from the build. To
reproduce it, run the binary in an Atari TOS emulator such as
[Hatari](https://hatari.tuxfamily.org/) with an
[EmuTOS](https://emutos.github.io/) ROM (`hatari --tos emutos-pal.img HELLO.PRG`);
it opens a `form_alert` dialog with the version strings, then exits.
