// Zig "hello" for the original Macintosh System 1.0 (Mac 128K, MC68000).
//
// The Macintosh sibling of atari-tos/zig: a modal NoteAlert dialog showing the
// Zig + LLVM versions under a populated menu bar, then a clean return to the
// Finder. Where the Atari port talks to AES via trap #2, here every call is a
// Macintosh Toolbox A-line trap ($Axxx) using the Pascal calling convention
// (caller pushes args; the trap removes them). No stdlib, no C glue — the
// equivalent of mactraps.c, inlined in Zig.
//
// A classic Mac CODE segment is loaded at an arbitrary address and is NOT
// relocated, so all code must be PC-relative (no absolute jsr/jmp, no R_68K_32).
// `make check-relocs` gates the build on that.

const builtin = @import("builtin");
const build_info = @import("build_info.zig");

// Toolbox traps trash D0-D2/A0-A1 and the condition codes (Inside Macintosh:
// "Register A2-A6/D3-D7 preserved"); declare that on every trap.
const TRAP_CLOBBER = .{
    .memory = true, .ccr = true,
    .d0 = true, .d1 = true, .d2 = true, .a0 = true, .a1 = true,
};

// ---------- QuickDraw / Toolbox init traps ----------

// QuickDraw globals: ~206 bytes with thePort LAST (offset 202). InitGraf is
// handed &thePort, stores it at 0(A5), and reaches every other global at a
// negative offset from there. Must be loaded, writable, PC-relative RAM, so it
// goes in .data via a nonzero initializer (an all-zero static would land in
// unloaded .bss).
var qd_globals: [208]u8 = [_]u8{1} ++ [_]u8{0} ** 207;
const QD_THEPORT: *anyopaque = @ptrCast(&qd_globals[202]);

fn initGraf(globals: *anyopaque) void {
    asm volatile (
        \\move.l %[g],-(%sp)
        \\.short 0xA86E
        :
        : [g] "r" (globals),
        : TRAP_CLOBBER);
}
fn initFonts() void { asm volatile (".short 0xA8FE" ::: TRAP_CLOBBER); }
fn initWindows() void { asm volatile (".short 0xA912" ::: TRAP_CLOBBER); }
fn initMenus() void { asm volatile (".short 0xA930" ::: TRAP_CLOBBER); }
fn teInit() void { asm volatile (".short 0xA9CC" ::: TRAP_CLOBBER); }
fn initCursor() void { asm volatile (".short 0xA850" ::: TRAP_CLOBBER); }
fn initDialogs(resume_proc: ?*anyopaque) void {
    asm volatile (
        \\move.l %[r],-(%sp)
        \\.short 0xA97B
        :
        : [r] "r" (resume_proc),
        : TRAP_CLOBBER);
}

// ---------- Menu Manager ----------

fn newMenu(id: i16, title: *const anyopaque) *anyopaque {
    // NewMenu returns a 4-byte MenuHandle; reserve result space as two words.
    return asm volatile (
        \\move.w #0,-(%sp)
        \\move.w #0,-(%sp)
        \\move.w %[id],-(%sp)
        \\move.l %[t],-(%sp)
        \\.short 0xA931
        \\move.l (%sp)+,%[ret]
        : [ret] "=r" (-> *anyopaque),
        : [id] "r" (id), [t] "r" (title),
        : TRAP_CLOBBER);
}
fn appendMenu(menu: *anyopaque, items: *const anyopaque) void {
    asm volatile (
        \\move.l %[m],-(%sp)
        \\move.l %[i],-(%sp)
        \\.short 0xA933
        :
        : [m] "r" (menu), [i] "r" (items),
        : TRAP_CLOBBER);
}
fn insertMenu(menu: *anyopaque, before: i16) void {
    asm volatile (
        \\move.l %[m],-(%sp)
        \\move.w %[b],-(%sp)
        \\.short 0xA935
        :
        : [m] "r" (menu), [b] "r" (before),
        : TRAP_CLOBBER);
}
fn drawMenuBar() void { asm volatile (".short 0xA937" ::: TRAP_CLOBBER); }

// ---------- Dialog Manager ----------

// ParamText(p0,p1,p2,p3: Str255) — p0 pushed first (ends up highest address).
fn paramText(p0: *const anyopaque, p1: *const anyopaque, p2: *const anyopaque, p3: *const anyopaque) void {
    asm volatile (
        \\move.l %[p0],-(%sp)
        \\move.l %[p1],-(%sp)
        \\move.l %[p2],-(%sp)
        \\move.l %[p3],-(%sp)
        \\.short 0xA98B
        :
        : [p0] "r" (p0), [p1] "r" (p1), [p2] "r" (p2), [p3] "r" (p3),
        : TRAP_CLOBBER);
}

// FUNCTION NoteAlert(alertID: INTEGER; filterProc: ProcPtr): INTEGER  ($A987)
fn noteAlert(alert_id: i16, filter: ?*anyopaque) i16 {
    return asm volatile (
        \\move.w #0,-(%sp)
        \\move.w %[id],-(%sp)
        \\move.l %[f],-(%sp)
        \\.short 0xA987
        \\move.w (%sp)+,%[ret]
        : [ret] "=r" (-> i16),
        : [id] "r" (alert_id), [f] "r" (filter),
        : TRAP_CLOBBER);
}

// PROCEDURE ExitToShell  ($A9F4) — returns to the Finder; never returns.
fn exitToShell() noreturn {
    asm volatile (".short 0xA9F4" ::: TRAP_CLOBBER);
    unreachable;
}

// ---------- Dialog resource text + menu strings ----------

// Classic Mac text breaks on carriage return (\r = 0x0D), honored in static
// dialog text. The banner is a compile-time constant, so the Str255 (length
// byte + bytes) is assembled at comptime — no runtime copy, so the scaled-index
// byte-loop hazard that forced -O0 in the C port simply never arises here.
const VERSION_PSTR = blk: {
    const t = "Built with:\rzig " ++ builtin.zig_version_string ++ "\r" ++ build_info.llvm_version;
    break :blk [_]u8{@intCast(t.len)} ++ t.*;
};
const EMPTY_PSTR = [_]u8{ 0, 0 };

// Dummy menus so the bar isn't blank: Apple (logo char 0x14) + File + Edit.
// Constant Pascal strings (length byte first).
const MENU_APPLE_TITLE = [_]u8{ 1, 0x14 };
const MENU_APPLE_ITEMS = "\x0fAbout this demo";
const MENU_FILE_TITLE = "\x04File";
const MENU_FILE_ITEMS = "\x04Quit";
const MENU_EDIT_TITLE = "\x04Edit";

// ---------- Entry point ----------

export fn _start() callconv(.c) noreturn {
    initGraf(QD_THEPORT);
    initFonts();
    initWindows();
    initMenus();
    teInit();
    initDialogs(null);
    initCursor();

    // Populate the menu bar. Edit has no items (titles are all the screenshot
    // needs; AppendMenu with an empty string corrupts the menu).
    var m = newMenu(1, &MENU_APPLE_TITLE);
    appendMenu(m, MENU_APPLE_ITEMS);
    insertMenu(m, 0);
    m = newMenu(2, MENU_FILE_TITLE);
    appendMenu(m, MENU_FILE_ITEMS);
    insertMenu(m, 0);
    m = newMenu(3, MENU_EDIT_TITLE);
    insertMenu(m, 0);
    drawMenuBar();

    paramText(&VERSION_PSTR, &EMPTY_PSTR, &EMPTY_PSTR, &EMPTY_PSTR);
    _ = noteAlert(128, null);
    exitToShell();
}
