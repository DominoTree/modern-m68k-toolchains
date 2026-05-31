# Build HELLO.PRG for EmuTOS / Atari TOS on m68k via custom Zig + LLVM.
#
# Pipeline:
#   1. zig build-obj -> main.o (m68k object)
#   2. m68k-elf-ld --relocatable --script=prg.ld -> hello.elf
#   3. toslink -> HELLO.PRG (GEMDOS executable)

# Point M68K_PREFIX at your toolchain (binutils, toslink, zig, and llvm-config
# all resolve beneath it); override on the command line if yours differs.
M68K_PREFIX ?= /opt/m68k
ZIG := $(M68K_PREFIX)/zig-install/bin/zig
LD  := $(M68K_PREFIX)/bin/m68k-elf-ld
TOSLINK := $(M68K_PREFIX)/bin/toslink
LLVM_CONFIG := $(M68K_PREFIX)/llvm-install/bin/llvm-config

OBJ := main.o
ELF := hello.elf
PRG := HELLO.PRG
BUILD_INFO := src/build_info.zig

ZIG_FLAGS := -target m68k-freestanding-none -mcpu=M68000 \
             -O ReleaseSmall -fno-PIE -fno-PIC -fsingle-threaded -fstrip

.PHONY: all clean
all: $(PRG)

$(BUILD_INFO): $(LLVM_CONFIG)
	printf 'pub const llvm_version: [:0]const u8 = "LLVM %s";\n' "$$($(LLVM_CONFIG) --version)" > $@

$(OBJ): src/main.zig $(BUILD_INFO)
	$(ZIG) build-obj $(ZIG_FLAGS) -femit-bin=$@ src/main.zig

$(ELF): $(OBJ) prg.ld
	$(LD) --relocatable --gc-sections --script=prg.ld -o $@ $(OBJ)

# -s strips the PRG symbol table at the shared toslink layer, so all three
# Atari ports strip identically regardless of what each compiler removes
# upstream (-fstrip here only drops debug info / local symbols; globals like
# _start survive into the PRG without this).
$(PRG): $(ELF)
	$(TOSLINK) -s -o $@ $(ELF)

clean:
	rm -f $(OBJ) $(ELF) $(PRG) $(BUILD_INFO)
