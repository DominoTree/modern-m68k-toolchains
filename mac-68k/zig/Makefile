# Build a classic Macintosh System 1.0 application from Zig on m68k.
#
# Pipeline (mirrors mac-68k/swift, with a Zig front-end and no C glue):
#   1. zig build-obj      src/main.zig   -> main.o      (m68k ELF, PC-relative)
#   2. m68k-elf-ld (full static link, base 0)           -> app.elf
#   3. m68k-elf-objcopy -O binary                       -> app.bin (raw 68000 code)
#   4. tools/elf2appl.py wraps app.bin into CODE 0 + CODE 1 resources and emits
#      a MacBinary II file (type 'APPL', creator 'SWFT')  -> HELLO.bin
#
# Point M68K_PREFIX at your toolchain (zig, binutils, llvm-config all resolve
# beneath it); override on the command line if yours differs.

M68K_PREFIX ?= /opt/m68k
ZIG         := $(M68K_PREFIX)/zig-install/bin/zig
LD          := $(M68K_PREFIX)/bin/m68k-elf-ld
OBJCOPY     := $(M68K_PREFIX)/bin/m68k-elf-objcopy
OBJDUMP     := $(M68K_PREFIX)/bin/m68k-elf-objdump
LLVM_CONFIG := $(M68K_PREFIX)/llvm-install/bin/llvm-config

# A classic Mac CODE segment is loaded at an arbitrary address and is NOT
# relocated, so the code must be PC-relative. Zig's default freestanding m68k
# codegen already emits PC-relative control flow and data loads (no absolute
# R_68K_32, no absolute jsr/jmp) — `make check-relocs` gates on that.
ZIG_FLAGS := -target m68k-freestanding-none -mcpu=M68000 \
             -O ReleaseSmall -fsingle-threaded

OBJ        := main.o
ELF        := app.elf
BIN        := app.bin
APP        := HELLO.bin
RSRC       := HELLO.rsrc
BUILD_INFO := src/build_info.zig

# Language-agnostic Mac output stage (CODE-resource packaging, MFS/HFS disk
# writer, link script, 68000-safety check) is shared by all three Mac ports.
COMMON    := ../common
TOOLS     := $(COMMON)/tools
RELOC_DEP := $(ELF)   # prerequisite consumed by common/check-relocs.mk

# SYSDISK - a bootable System 1.0 (400K) disk image; if set, `make disk` drops
#           HELLO onto a copy of it. If unset, a fresh non-bootable 400K volume
#           holding just the app is produced (for inspection).
SYSDISK ?=
DISK    := build/boot.dsk

.PHONY: all clean check-relocs disk
all: $(APP)

$(BUILD_INFO): $(LLVM_CONFIG)
	printf 'pub const llvm_version: [:0]const u8 = "LLVM %s";\n' "$$($(LLVM_CONFIG) --version)" > $@

$(OBJ): src/main.zig $(BUILD_INFO)
	$(ZIG) build-obj $(ZIG_FLAGS) -femit-bin=$@ src/main.zig

$(ELF): $(OBJ) $(COMMON)/app.ld
	$(LD) --gc-sections -static --script=$(COMMON)/app.ld -o $@ $(OBJ)

$(BIN): $(ELF)
	$(OBJCOPY) -O binary -j .text -j .rodata $< $@

# check-relocs is a prerequisite so every packaged build is verified 68000-safe
# (the M68k backend can nondeterministically emit a 68020 scaled-index mode).
$(APP): $(BIN) check-relocs $(TOOLS)/elf2appl.py
	python3 $(TOOLS)/elf2appl.py --elf $(ELF) --bin $(BIN) --out $@ --rsrc-out $(RSRC) --dialog

# check-relocs target is shared by all three Mac ports:
include $(COMMON)/check-relocs.mk

# Inject the app onto a disk image (machfs/MFS; 400K-capable).
disk: $(APP)
	@mkdir -p build
ifeq ($(strip $(SYSDISK)),)
	python3 $(TOOLS)/inject.py --rsrc $(RSRC) --out "$(DISK)"
	@echo "NOTE: $(DISK) is a fresh non-bootable volume. Set SYSDISK=<System 1.0 image> for a bootable disk."
else
	python3 $(TOOLS)/inject.py --rsrc $(RSRC) --base "$(SYSDISK)" --out "$(DISK)"
endif

clean:
	rm -f $(OBJ) $(ELF) $(BIN) $(APP) $(RSRC) $(BUILD_INFO)
	rm -rf build
