# Build a classic Macintosh System 1.0 application from Rust on m68k.
#
# Pipeline (mirrors mac-68k/swift, with a Rust front-end and no C glue):
#   1. cargo build --release   -> a full static base-0 ELF (app.ld via rustflags)
#   2. m68k-elf-objcopy -O binary                        -> app.bin (raw 68000 code)
#   3. tools/elf2appl.py wraps app.bin into CODE 0 + CODE 1 resources and emits
#      a MacBinary II file (type 'APPL', creator 'SWFT')   -> HELLO.bin
#
# cargo links with m68k-elf-ld (named in m68k-mac.json) and the link is gated on
# being 68000-safe by `make check-relocs`. m68k-elf-ld must be on PATH for the
# cargo link step; point M68K_PREFIX at the rest of your toolchain.

M68K_PREFIX ?= /opt/m68k
OBJCOPY     := $(M68K_PREFIX)/bin/m68k-elf-objcopy
OBJDUMP     := $(M68K_PREFIX)/bin/m68k-elf-objdump

ELF  := target/m68k-mac/release/rust-mac-hello
BIN  := app.bin
APP  := HELLO.bin
RSRC := HELLO.rsrc

# Language-agnostic Mac output stage (CODE-resource packaging, MFS/HFS disk
# writer, link script, 68000-safety check) is shared by all three Mac ports.
# (The link script itself is referenced from .cargo/config.toml, since cargo
# drives the link.)
COMMON    := ../common
TOOLS     := $(COMMON)/tools
RELOC_DEP := elf   # phony cargo target consumed by common/check-relocs.mk

# SYSDISK - a bootable System 1.0 (400K) disk image; if set, `make disk` drops
#           HELLO onto a copy of it.
SYSDISK ?=
DISK    := build/boot.dsk

.PHONY: all clean elf check-relocs disk
all: $(APP)

elf:
	cargo build --release

$(BIN): elf
	$(OBJCOPY) -O binary -j .text -j .rodata $(ELF) $(BIN)

# check-relocs is a prerequisite so every packaged build is verified 68000-safe.
$(APP): $(BIN) check-relocs $(TOOLS)/elf2appl.py
	python3 $(TOOLS)/elf2appl.py --elf $(ELF) --bin $(BIN) --out $(APP) --rsrc-out $(RSRC) --dialog

# check-relocs target is shared by all three Mac ports:
include $(COMMON)/check-relocs.mk

disk: $(APP)
	@mkdir -p build
ifeq ($(strip $(SYSDISK)),)
	python3 $(TOOLS)/inject.py --rsrc $(RSRC) --out "$(DISK)"
	@echo "NOTE: $(DISK) is a fresh non-bootable volume. Set SYSDISK=<System 1.0 image> for a bootable disk."
else
	python3 $(TOOLS)/inject.py --rsrc $(RSRC) --base "$(SYSDISK)" --out "$(DISK)"
endif

clean:
	cargo clean
	rm -f $(BIN) $(APP) $(RSRC)
	rm -rf build
