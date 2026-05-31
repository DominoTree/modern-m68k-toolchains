// Rust "hello" for the original Macintosh System 1.0 (Mac 128K, MC68000).
//
// The Macintosh sibling of atari-tos/rust, and the Rust counterpart of
// mac-68k/swift: a modal NoteAlert dialog showing the Rust + LLVM versions under
// a populated menu bar, then a clean return to the Finder. Where the Atari port
// talks to AES via trap #2, here every call is a Macintosh Toolbox A-line trap
// ($Axxx) using the Pascal calling convention (caller pushes args; the trap
// removes them). No std, no C glue — the equivalent of mactraps.c, inlined.
//
// A classic Mac CODE segment is loaded at an arbitrary address and is NOT
// relocated, so all code must be PC-relative (no absolute jsr/jmp, no R_68K_32).
// `make check-relocs` gates the build on that.

#![no_std]
#![no_main]
#![feature(asm_experimental_arch)]

use core::arch::asm;
use core::panic::PanicInfo;
use core::ptr::addr_of_mut;

// ---------- QuickDraw / Toolbox init traps ----------

// QuickDraw globals: ~206 bytes with thePort LAST (offset 202). InitGraf is
// handed &thePort, stores it at 0(A5), and reaches every other global at a
// negative offset from there. Must be loaded, writable, PC-relative RAM, so a
// nonzero initializer keeps it in .data (an all-zero static would land in
// unloaded .bss).
static mut QD_GLOBALS: [u8; 208] = {
    let mut a = [0u8; 208];
    a[0] = 1;
    a
};

unsafe fn initgraf(globals: *mut u8) {
    asm!(
        "move.l {g},-(%sp)",
        ".short 0xA86E",
        g = in(reg) globals,
        out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _,
    );
}
unsafe fn initfonts()   { asm!(".short 0xA8FE", out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _); }
unsafe fn initwindows() { asm!(".short 0xA912", out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _); }
unsafe fn initmenus()   { asm!(".short 0xA930", out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _); }
unsafe fn teinit()      { asm!(".short 0xA9CC", out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _); }
unsafe fn initcursor()  { asm!(".short 0xA850", out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _); }

unsafe fn initdialogs(resume_proc: *mut u8) {
    asm!(
        "move.l {r},-(%sp)",
        ".short 0xA97B",
        r = in(reg) resume_proc,
        out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _,
    );
}

// ---------- Menu Manager ----------

unsafe fn newmenu(id: i16, title: *const u8) -> *mut u8 {
    // NewMenu returns a 4-byte MenuHandle; reserve result space as two words.
    let h: *mut u8;
    asm!(
        "move.w #0,-(%sp)",
        "move.w #0,-(%sp)",
        "move.w {id},-(%sp)",
        "move.l {t},-(%sp)",
        ".short 0xA931",
        "move.l (%sp)+,{h}",
        id = in(reg) id,
        t = in(reg) title,
        h = out(reg) h,
        out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _,
    );
    h
}
unsafe fn appendmenu(menu: *mut u8, items: *const u8) {
    asm!(
        "move.l {m},-(%sp)",
        "move.l {i},-(%sp)",
        ".short 0xA933",
        m = in(reg) menu,
        i = in(reg) items,
        out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _,
    );
}
unsafe fn insertmenu(menu: *mut u8, before: i16) {
    asm!(
        "move.l {m},-(%sp)",
        "move.w {b},-(%sp)",
        ".short 0xA935",
        m = in(reg) menu,
        b = in(reg) before,
        out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _,
    );
}
unsafe fn drawmenubar() { asm!(".short 0xA937", out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _); }

// ---------- Dialog Manager ----------

// ParamText(p0,p1,p2,p3: Str255) — p0 pushed first (ends up highest address).
unsafe fn paramtext(p0: *const u8, p1: *const u8, p2: *const u8, p3: *const u8) {
    asm!(
        "move.l {p0},-(%sp)",
        "move.l {p1},-(%sp)",
        "move.l {p2},-(%sp)",
        "move.l {p3},-(%sp)",
        ".short 0xA98B",
        p0 = in(reg) p0,
        p1 = in(reg) p1,
        p2 = in(reg) p2,
        p3 = in(reg) p3,
        out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _,
    );
}

// FUNCTION NoteAlert(alertID: INTEGER; filterProc: ProcPtr): INTEGER  ($A987)
unsafe fn notealert(alert_id: i16, filter: *mut u8) -> i16 {
    let r: i16;
    asm!(
        "move.w #0,-(%sp)",
        "move.w {id},-(%sp)",
        "move.l {f},-(%sp)",
        ".short 0xA987",
        "move.w (%sp)+,{r}",
        id = in(reg) alert_id,
        f = in(reg) filter,
        r = out(reg) r,
        out("d0") _, out("d1") _, out("d2") _, out("a0") _, out("a1") _,
    );
    r
}

// PROCEDURE ExitToShell  ($A9F4) — returns to the Finder; never returns.
unsafe fn exit_to_shell() -> ! {
    asm!(".short 0xA9F4", options(noreturn));
}

// ---------- Dialog text + menu strings ----------

// Classic Mac text breaks on carriage return (\r = 0x0D), honored in static
// dialog text. The banner is built at compile time, so the Str255 (length byte
// + bytes) is a const — no runtime byte loop, so the scaled-index 68020 hazard
// the C port works around with `optnone` never arises. Version strings come from
// build.rs (host `rustc -vV`).
const VERSION_TEXT: &str = concat!(
    "Built with:\r",
    env!("BUILD_RUSTC"),
    "\r",
    env!("BUILD_LLVM"),
);
const VLEN: usize = VERSION_TEXT.len();
static VERSION_PSTR: [u8; VLEN + 1] = {
    let b = VERSION_TEXT.as_bytes();
    let mut a = [0u8; VLEN + 1];
    a[0] = VLEN as u8;
    let mut i = 0;
    while i < VLEN {
        a[i + 1] = b[i];
        i += 1;
    }
    a
};
static EMPTY_PSTR: [u8; 2] = [0, 0];

// Dummy menus so the bar isn't blank: Apple (logo char 0x14) + File + Edit.
static MENU_APPLE_TITLE: [u8; 2] = [1, 0x14];
static MENU_APPLE_ITEMS: &[u8] = b"\x0fAbout this demo";
static MENU_FILE_TITLE: &[u8] = b"\x04File";
static MENU_FILE_ITEMS: &[u8] = b"\x04Quit";
static MENU_EDIT_TITLE: &[u8] = b"\x04Edit";

// ---------- Entry point ----------

#[no_mangle]
#[link_section = ".text._start"]
pub unsafe extern "C" fn _start() -> ! {
    initgraf((addr_of_mut!(QD_GLOBALS) as *mut u8).add(202));
    initfonts();
    initwindows();
    initmenus();
    teinit();
    initdialogs(core::ptr::null_mut());
    initcursor();

    // Populate the menu bar. Edit has no items (titles are all the screenshot
    // needs; AppendMenu with an empty string corrupts the menu).
    let mut m = newmenu(1, MENU_APPLE_TITLE.as_ptr());
    appendmenu(m, MENU_APPLE_ITEMS.as_ptr());
    insertmenu(m, 0);
    m = newmenu(2, MENU_FILE_TITLE.as_ptr());
    appendmenu(m, MENU_FILE_ITEMS.as_ptr());
    insertmenu(m, 0);
    m = newmenu(3, MENU_EDIT_TITLE.as_ptr());
    insertmenu(m, 0);
    drawmenubar();

    paramtext(
        VERSION_PSTR.as_ptr(),
        EMPTY_PSTR.as_ptr(),
        EMPTY_PSTR.as_ptr(),
        EMPTY_PSTR.as_ptr(),
    );
    let _ = notealert(128, core::ptr::null_mut());
    exit_to_shell()
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    unsafe { exit_to_shell() }
}

// LLVM may emit calls to `abort` along the panic/unreachable path. Resolve to
// _ExitToShell so the program returns cleanly to the Finder.
#[no_mangle]
unsafe extern "C" fn abort() -> ! {
    exit_to_shell()
}

// LLVM lowers struct zero-init to a `memset` call. compiler_builtins ships a
// memset shim behind the `mem` feature, but its thunk uses `bra.l`, a 68020+
// instruction unavailable on 68000. Provide 68000-safe versions.
#[no_mangle]
unsafe extern "C" fn memset(dest: *mut u8, c: i32, n: usize) -> *mut u8 {
    let mut i = 0;
    while i < n {
        *dest.add(i) = c as u8;
        i += 1;
    }
    dest
}
#[no_mangle]
unsafe extern "C" fn memcpy(dest: *mut u8, src: *const u8, n: usize) -> *mut u8 {
    let mut i = 0;
    while i < n {
        *dest.add(i) = *src.add(i);
        i += 1;
    }
    dest
}
