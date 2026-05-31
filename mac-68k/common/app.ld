/* Linker script for a single-CODE-segment classic Macintosh application.
 *
 * Unlike a GEMDOS .PRG (which carries a relocation table the loader applies),
 * a classic Mac CODE segment is loaded at an arbitrary address with NO fixup of
 * absolute references inside it. So the code must be position-independent:
 * intra-segment control flow via PC-relative BSR/JMP, no absolute R_68K_32
 * references. We link fully at base 0 and `make` then inspects the residual
 * relocations to confirm none are absolute. _start must be first so its offset
 * within the segment is known (0 in the raw blob; the packager accounts for the
 * 4-byte CODE segment header).
 */

ENTRY(_start)

SECTIONS
{
    . = 0;

    .text : ALIGN(2) {
        *(.text._start)
        *(.text)
        *(.text.*)
        . = ALIGN(2);
    }

    /* rodata/data fold into the same single segment (referenced PC-relative),
     * but as a section distinct from .text so `make check-relocs` can
     * disassemble code only and not trip over string literals that happen to
     * decode as instruction words. Laid contiguously after .text, so the
     * extracted blob (objcopy -j .text -j .rodata) is byte-identical to a
     * fully-folded layout. */
    .rodata : ALIGN(2) {
        *(.rodata)
        *(.rodata.*)
        . = ALIGN(2);
        *(.data)
        *(.data.*)
        . = ALIGN(2);
    }

    .bss (NOLOAD) : ALIGN(2) {
        *(.bss)
        *(.bss.*)
        *(COMMON)
        . = ALIGN(2);
    }

    /DISCARD/ : {
        *(.comment)
        *(.note.*)
        *(.eh_frame*)
        *(.debug*)
        *(.swift_modhash*)
        *(.swift*)
        *(.llvm*)
        *(.ARM.exidx*)
        *(.linker-options*)
        *(.group)
    }
}
