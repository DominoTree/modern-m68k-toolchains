/* GEMDOS .prg linker script. Sections laid out for toslink ELF -> .prg. */

ENTRY(_start)

SECTIONS
{
    .text : ALIGN(4) {
        *(.text._start)
        *(.text)
        *(.text.*)
        /* Pad .text to 16 so the 16-aligned .data below sits flush against it.
         * toslink copies sections by size but resolves PC-relative relocs by
         * address, so an inter-section gap (Swift's .rodata.str1.16 constants
         * force one) would offset every text->data reference by the gap. This
         * is why Swift string literals landed ~15 bytes off before the pad. */
        . = ALIGN(16);
    }

    .data : ALIGN(4) {
        *(.data)
        *(.data.*)
        *(.rodata)
        *(.rodata.*)
        . = ALIGN(4);
    }

    .bss : ALIGN(4) {
        *(.bss)
        *(.bss.*)
        . = ALIGN(4);
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
