# Build HELLO.PRG for EmuTOS / Atari TOS on m68k via custom Swift + LLVM.
#
# Pipeline:
#   1. swiftc -enable-experimental-feature Embedded -> main.o (m68k)
#   2. clang -target m68k-none-none-elf -> gemdos.o (m68k C with inline trap asm)
#   3. m68k-elf-ld --relocatable --script=prg.ld -> hello.elf
#   4. toslink -> HELLO.PRG (GEMDOS executable)

# Point SWIFT_PREFIX / M68K_PREFIX at your local toolchain builds (override on
# the command line, e.g. `make M68K_PREFIX=/path/to/m68k`).
SWIFT_PREFIX ?= /opt/swift-m68k
M68K_PREFIX  ?= /opt/m68k
SWIFTC       := $(SWIFT_PREFIX)/swift-build/bin/swiftc
CLANG        := $(SWIFT_PREFIX)/llvm-install/bin/clang
# Host-platform subdir of the Swift runtime libs swiftc links against
# (linux, freebsd, macosx, …):
SWIFT_HOST   ?= linux
SWIFT_LDPATH := $(SWIFT_PREFIX)/lib/swift/$(SWIFT_HOST)
SWIFT_RES    := $(SWIFT_PREFIX)/swift-build/lib/swift
LD           := $(M68K_PREFIX)/bin/m68k-elf-ld
TOSLINK      := $(M68K_PREFIX)/bin/toslink

SWIFT_OBJ := main.o
C_OBJ     := gemdos.o
ELF       := hello.elf
PRG       := HELLO.PRG

# Flags chosen to mirror the size/feature config of the Rust and Zig ports:
#   -function-sections      per-function sections so --gc-sections at link time
#                           can drop unreachable code (Rust/Zig do this by default;
#                           without it Swift emits one .text and --gc-sections is a
#                           no-op — the single biggest size win here, ~2080B->496B).
#   -remove-runtime-asserts + -assert-config Unchecked
#                           drop overflow/precondition traps — matches Zig
#                           ReleaseSmall and Rust release (no overflow checks).
SWIFT_FLAGS := -target m68k-none-none-elf -enable-experimental-feature Embedded \
               -Osize -wmo -parse-as-library -resource-dir $(SWIFT_RES) -sdk / \
               -Xfrontend -function-sections \
               -Xfrontend -remove-runtime-asserts \
               -Xfrontend -assert-config -Xfrontend Unchecked \
               -Xfrontend -disable-stack-protector \
               -Xcc -fno-stack-protector \
               -Xllvm -relocation-model=static
C_FLAGS     := -target m68k-none-none-elf -mcpu=M68000 -ffreestanding -fno-pic \
               -Os -ffunction-sections -fdata-sections \
               -nostdlib -nostdinc -isystem $(M68K_PREFIX)/binutils-install/m68k-elf/include \
               -isystem $(SWIFT_PREFIX)/llvm-install/lib/clang/21/include

.PHONY: all clean
all: $(PRG)

$(SWIFT_OBJ): src/main.swift
	LD_LIBRARY_PATH=$(SWIFT_LDPATH) $(SWIFTC) $(SWIFT_FLAGS) -c $< -o $@

$(C_OBJ): src/gemdos.c
	$(CLANG) $(C_FLAGS) -c $< -o $@

$(ELF): $(SWIFT_OBJ) $(C_OBJ) prg.ld
	$(LD) --relocatable --gc-sections --script=prg.ld -o $@ $(SWIFT_OBJ) $(C_OBJ)

# -s strips the PRG symbol table (mirror Rust strip=true / Zig -fstrip). Done in
# toslink, not objcopy: the relocatable ELF's symbols are needed to resolve the
# GEMDOS fixup table, so stripping the ELF first would drop relocations and
# break loading at a non-zero address.
$(PRG): $(ELF)
	$(TOSLINK) -s -o $@ $(ELF)

clean:
	rm -f $(SWIFT_OBJ) $(C_OBJ) $(ELF) $(PRG)
