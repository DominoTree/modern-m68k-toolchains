# Shared `check-relocs` recipe for the classic-Mac ports (swift / zig / rust).
#
# A classic Mac CODE segment is loaded at an arbitrary address and is NOT
# relocated, so the linked image must be fully PC-relative and 68000-only. This
# recipe disassembles it and asserts: no absolute jsr/jmp, no residual
# relocations, no 68020+ instructions. The disassembly scans are scoped to
# .text so rodata string literals aren't decoded as instructions.
#
# The including Makefile must define:
#   OBJDUMP    - path to m68k-elf-objdump
#   ELF        - the linked ELF to inspect
#   RELOC_DEP  - prerequisite that (re)builds $(ELF): the ELF file for the
#                swift/zig ports, or a phony `elf` (cargo) target for rust.

check-relocs: $(RELOC_DEP)
	@abs=$$($(OBJDUMP) -d -j .text $(ELF) | grep -cE '\b4e(b9|f9)\b'); \
	rel=$$($(OBJDUMP) -r $(ELF) | grep -cE 'R_68K'); \
	new=$$($(OBJDUMP) -d -j .text $(ELF) | sed 's/^[^\t]*\t[^\t]*\t//' | \
	    grep -cwiE 'bfextu|bfins|bfclr|bfset|muls\.l|mulu\.l|divs\.l|divu\.l|extb\.l|rtd|chk2|cmp2|cas|cas2|pack|unpk|bkpt|callm|movec|trapcc'); \
	bad=$$($(OBJDUMP) -d -j .text -M m68000 $(ELF) | grep -E '\.short' | grep -viE '0xa[0-9a-f]{3}' | wc -l | tr -d ' '); \
	echo "absolute jsr/jmp (4eb9/4ef9): $$abs (want 0)"; \
	echo "residual relocations:        $$rel (want 0)"; \
	echo "68020+ mnemonics:            $$new (want 0)"; \
	echo "undecodable-on-68000 words:  $$bad (want 0; excludes A-traps)"; \
	if [ "$$abs" -ne 0 ] || [ "$$rel" -ne 0 ] || [ "$$new" -ne 0 ] || [ "$$bad" -ne 0 ]; then \
	    echo "FAIL: image is not relocation-free 68000-only"; \
	    $(OBJDUMP) -d -j .text -M m68000 $(ELF) | grep -E '\.short' | grep -viE '0xa[0-9a-f]{3}'; exit 1; \
	else echo "PASS: PC-relative, relocation-free, 68000-only"; fi
