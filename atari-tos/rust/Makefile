# Build HELLO.PRG for EmuTOS / Atari TOS on m68k.
#
# Pipeline:
#   1. cargo build --release -> ELF in target/m68k-tos/release/
#   2. toslink converts the ELF to a GEMDOS .prg

ELF := target/m68k-tos/release/rust-tos-hello
PRG := HELLO.PRG

.PHONY: all clean elf prg

all: prg

elf:
	cargo build --release

# -s strips the PRG symbol table at the shared toslink layer, so all three
# Atari ports strip identically regardless of what each compiler removes
# upstream (Cargo's strip=true drops debug info / local symbols; globals like
# _start survive into the PRG without this).
prg: elf
	toslink -s -o $(PRG) $(ELF)

clean:
	cargo clean
	rm -f $(PRG)
