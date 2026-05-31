# Build a classic Macintosh System 1.0 application from Embedded Swift on m68k.
#
# Pipeline:
#   1. swiftc (Embedded)      src/main.swift   -> main.o      (m68k ELF)
#   2. clang  -target m68k    src/mactraps.c   -> mactraps.o  (A-trap glue)
#   3. m68k-elf-ld (full link, base 0)         -> app.elf
#   4. m68k-elf-objcopy -O binary              -> app.bin     (raw 68000 code)
#   5. tools/elf2appl.py wraps app.bin into CODE 0 + CODE 1 resources and emits
#      a MacBinary II file (type 'APPL', creator 'SWFT') -> HELLO.bin
#
# Point SWIFT_PREFIX / M68K_PREFIX below at your local toolchain builds
# (override on the command line, e.g. `make SWIFT_PREFIX=/path/to/swift-m68k`).

SWIFT_PREFIX ?= /opt/swift-m68k
M68K_PREFIX  ?= /opt/m68k

SWIFTC       := $(SWIFT_PREFIX)/swift-build/bin/swiftc
SWIFT_RES    := $(SWIFT_PREFIX)/swift-build/lib/swift
# Host-platform subdir of the Swift runtime libs swiftc links against
# (linux, freebsd, macosx, …):
SWIFT_HOST   ?= linux
SWIFT_LDPATH := $(SWIFT_PREFIX)/lib/swift/$(SWIFT_HOST)
CLANG        := $(SWIFT_PREFIX)/llvm-install/bin/clang
LD           := $(M68K_PREFIX)/bin/m68k-elf-ld
OBJCOPY      := $(M68K_PREFIX)/bin/m68k-elf-objcopy
OBJDUMP      := $(M68K_PREFIX)/bin/m68k-elf-objdump

# Relocation model: classic Mac CODE segments are not relocated at load, so we
# want PC-relative codegen (no absolute R_68K_32 refs). `make check-relocs`
# verifies this; flip to pic if static leaves absolute relocations.
RELOC_MODEL  := static

SWIFT_FLAGS := -target m68k-none-none-elf -enable-experimental-feature Embedded \
               -Osize -wmo -parse-as-library -resource-dir $(SWIFT_RES) -sdk / \
               -Xfrontend -function-sections \
               -Xfrontend -remove-runtime-asserts \
               -Xfrontend -assert-config -Xfrontend Unchecked \
               -Xfrontend -disable-stack-protector \
               -Xfrontend -target-cpu -Xfrontend M68000 \
               -Xcc -fno-stack-protector -Xcc -mcpu=M68000 \
               -Xllvm -relocation-model=$(RELOC_MODEL)

# -fpic so the C glue is PC-relative too (classic Mac CODE segments load at an
# arbitrary address and are not relocated). With a full static link the PLT16
# call relocations resolve to direct PC-relative branches; no GOT is needed
# because the glue has no global data.
# -fno-builtin: stop clang from pattern-matching loops into optimized mem*/
# clamp sequences that use a scaled-index addressing mode (68020+ only, faults
# as an illegal instruction on the 68000). We provide our own mem* anyway.
C_FLAGS := -target m68k-none-none-elf -mcpu=M68000 -ffreestanding -fpic \
           -fno-builtin -Os -ffunction-sections -fdata-sections -nostdlib -nostdinc \
           -isystem $(SWIFT_PREFIX)/llvm-install/lib/clang/21/include

SWIFT_OBJ := main.o
C_OBJ     := mactraps.o
ELF       := app.elf
BIN       := app.bin
APP       := HELLO.bin
RSRC      := HELLO.rsrc

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

$(SWIFT_OBJ): src/main.swift
	LD_LIBRARY_PATH=$(SWIFT_LDPATH) $(SWIFTC) $(SWIFT_FLAGS) -c $< -o $@

$(C_OBJ): src/mactraps.c
	$(CLANG) $(C_FLAGS) -c $< -o $@

$(ELF): $(SWIFT_OBJ) $(C_OBJ) $(COMMON)/app.ld
	$(LD) --gc-sections -static --script=$(COMMON)/app.ld -o $@ $(SWIFT_OBJ) $(C_OBJ)

$(BIN): $(ELF)
	$(OBJCOPY) -O binary -j .text -j .rodata $< $@

# check-relocs is a prerequisite so every packaged build is verified 68000-safe
# (the M68k backend can nondeterministically emit a 68020 scaled-index mode).
$(APP): $(BIN) check-relocs $(TOOLS)/elf2appl.py
	python3 $(TOOLS)/elf2appl.py --elf $(ELF) --bin $(BIN) --out $@ --rsrc-out $(RSRC) --dialog

# check-relocs target is shared by all three Mac ports:
include $(COMMON)/check-relocs.mk

# Inject the app onto a disk image (machfs/MFS; 400K-capable, unlike hfsutils).
disk: $(APP)
	@mkdir -p build
ifeq ($(strip $(SYSDISK)),)
	python3 $(TOOLS)/inject.py --rsrc $(RSRC) --out "$(DISK)"
	@echo "NOTE: $(DISK) is a fresh non-bootable volume. Set SYSDISK=<System 1.0 image> for a bootable disk."
else
	python3 $(TOOLS)/inject.py --rsrc $(RSRC) --base "$(SYSDISK)" --out "$(DISK)"
endif

clean:
	rm -f $(SWIFT_OBJ) $(C_OBJ) $(ELF) $(BIN) $(APP) $(RSRC)
	rm -rf build
