// Macintosh Toolbox A-line trap glue + Embedded-Swift runtime stubs for
// classic 68000 Macintosh (System 1.0, Mac 128K, 64K ROM).
//
// Toolbox traps are single 16-bit "A-line" instruction words ($Axxx). The
// 68000 has no opcode there, so the line-1010 emulator exception fires and the
// Trap Dispatcher vectors to the ROM routine. Toolbox traps ($A800-$AFFF) use
// the Pascal calling convention: arguments pushed by the caller, and the
// (Pascal) routine removes its own arguments before returning.
//
// clang/LLVM does not understand MPW's `pascal` / `#pragma parameter`, so we
// emit the trap words ourselves with `.short` and set up the stack by hand.
// Everything here stays within the plain MC68000 instruction set.

#include <stdint.h>

// PROCEDURE SysBeep(duration: INTEGER);   trap $A9C8
// Push the 2-byte duration; the trap pops it (Pascal convention).
__attribute__((noinline))
void sysbeep(int16_t duration) {
    __asm__ volatile (
        "move.w %0, -(%%sp)\n\t"
        ".short 0xA9C8\n\t"
        :
        : "r"(duration)
        : "memory", "cc", "d0", "d1", "d2", "a0", "a1"
    );
}

// PROCEDURE ExitToShell;   trap $A9F4   (returns to the Finder; never returns)
__attribute__((noinline, noreturn))
void exit_to_shell(void) {
    __asm__ volatile (
        ".short 0xA9F4\n\t"
        ::: "memory"
    );
    __builtin_unreachable();
}

// --- QuickDraw + Dialog Manager glue (Milestone 2: version alert) -----------
//
// All Toolbox traps below use the Pascal convention: for a function the caller
// reserves result space first, then pushes args left-to-right; INTEGER/Boolean
// are words, pointers are longs; the trap removes its own arguments.
//
// Standard init order: InitGraf -> InitFonts -> InitWindows -> InitMenus ->
// TEInit -> InitDialogs -> InitCursor. All present in the 1984 64K ROM.

#define ATRAP_CLOBBER "memory", "cc", "d0", "d1", "d2", "a0", "a1"

// QuickDraw globals: ~206 bytes, with thePort as the LAST field (offset 202).
// InitGraf is passed &thePort and stores it at 0(A5); QuickDraw then reaches
// every other global at a negative offset from there. The buffer must be in
// loaded, writable, PC-relative-addressable RAM, so it is forced into .data
// with a nonzero initializer (an all-zero static would land in unloaded .bss).
__attribute__((aligned(2))) static unsigned char qd_globals[208] = {1};
#define QD_THEPORT (&qd_globals[202])

static void initgraf(void *globals) {
    __asm__ volatile("move.l %0,-(%%sp)\n\t.short 0xA86E\n\t"
                     : : "a"(globals) : ATRAP_CLOBBER);
}
static void initfonts(void)   { __asm__ volatile(".short 0xA8FE\n\t" ::: ATRAP_CLOBBER); }
static void initwindows(void) { __asm__ volatile(".short 0xA912\n\t" ::: ATRAP_CLOBBER); }
static void initmenus(void)   { __asm__ volatile(".short 0xA930\n\t" ::: ATRAP_CLOBBER); }
static void teinit(void)      { __asm__ volatile(".short 0xA9CC\n\t" ::: ATRAP_CLOBBER); }
static void initcursor(void)  { __asm__ volatile(".short 0xA850\n\t" ::: ATRAP_CLOBBER); }

static void initdialogs(void *resumeProc) {
    __asm__ volatile("move.l %0,-(%%sp)\n\t.short 0xA97B\n\t"
                     : : "a"(resumeProc) : ATRAP_CLOBBER);
}

// PROCEDURE ParamText(p0,p1,p2,p3: Str255) — four string pointers, p0 pushed
// first (ends up at the highest address), p3 nearest SP.
static void paramtext(const void *p0, const void *p1, const void *p2, const void *p3) {
    __asm__ volatile(
        "move.l %0,-(%%sp)\n\t"
        "move.l %1,-(%%sp)\n\t"
        "move.l %2,-(%%sp)\n\t"
        "move.l %3,-(%%sp)\n\t"
        ".short 0xA98B\n\t"
        : : "a"(p0), "a"(p1), "a"(p2), "a"(p3) : ATRAP_CLOBBER);
}

// FUNCTION NoteAlert(alertID: INTEGER; filterProc: ProcPtr): INTEGER
// (same signature as StopAlert/CautionAlert; differs only in the trap word and
// the system icon drawn: $A986 StopAlert, $A987 NoteAlert, $A988 CautionAlert.)
static short notealert(short alertID, void *filterProc) {
    short result;
    __asm__ volatile(
        "move.w #0,-(%%sp)\n\t"     // result space (reserve a word)
        "move.w %1,-(%%sp)\n\t"     // alertID
        "move.l %2,-(%%sp)\n\t"     // filterProc
        ".short 0xA987\n\t"         // _NoteAlert (note/asterisk icon)
        "move.w (%%sp)+,%0\n\t"     // pop result (item hit)
        : "=d"(result) : "d"(alertID), "a"(filterProc) : ATRAP_CLOBBER);
    return result;
}

// Dummy menus so the menu bar isn't blank: an Apple menu (logo char 0x14 in the
// Chicago system font) and a File menu. Constant Pascal strings (length byte
// first) in .rodata — no runtime copy, no Swift strings, so neither the
// scaled-index nor the static-string codegen bug applies.
static const char menu_apple_title[] = "\001\024";            // len 1, apple logo
static const char menu_apple_items[] = "\017About this demo"; // len 15
static const char menu_file_title[]  = "\004File";            // len 4
static const char menu_file_items[]  = "\004Quit";            // len 4
static const char menu_edit_title[]  = "\004Edit";            // len 4

// Menu Manager wrappers. NewMenu returns a 4-byte MenuHandle; its result space
// is reserved as two words (the m68k IAS rejects move.l #imm).
static void *newmenu(short id, const void *title) {
    void *h;
    __asm__ volatile(
        "move.w #0,-(%%sp)\n\t"      // result space (handle) hi word
        "move.w #0,-(%%sp)\n\t"      //                       lo word
        "move.w %1,-(%%sp)\n\t"      // menuID
        "move.l %2,-(%%sp)\n\t"      // title ptr
        ".short 0xA931\n\t"          // _NewMenu
        "move.l (%%sp)+,%0\n\t"      // pop MenuHandle
        : "=a"(h) : "d"(id), "a"(title) : ATRAP_CLOBBER);
    return h;
}
static void appendmenu(void *menu, const void *items) {
    __asm__ volatile(
        "move.l %0,-(%%sp)\n\t"
        "move.l %1,-(%%sp)\n\t"
        ".short 0xA933\n\t"          // _AppendMenu
        : : "a"(menu), "a"(items) : ATRAP_CLOBBER);
}
static void insertmenu(void *menu, short before) {
    __asm__ volatile(
        "move.l %0,-(%%sp)\n\t"
        "move.w %1,-(%%sp)\n\t"
        ".short 0xA935\n\t"          // _InsertMenu (before 0 = append at end)
        : : "a"(menu), "d"(before) : ATRAP_CLOBBER);
}
static void drawmenubar(void) { __asm__ volatile(".short 0xA937\n\t" ::: ATRAP_CLOBBER); }

// Pascal string assembled from the Swift-provided UTF-8 (forced into .data).
static unsigned char pstr[256] = {1};
static const unsigned char empty_pstr[2] = {0, 0};

// Show a modal NoteAlert (ALRT/DITL 128) whose text is the given bytes. The
// alert's StaticText is "^0", substituted via ParamText. The alert is modal and
// blocks until OK is clicked — exactly what we want for a headless screenshot.
// optnone: at -Os the M68k backend may pick a scaled-index addressing mode for
// the byte copy below, which is 68020+ only and faults as an illegal
// instruction on the 68000. -O0 codegen uses only simple register-indirect
// addressing and is deterministically 68000-safe. (LLVM's m68k integrated
// assembler is too limited to hand-write the loop in inline asm: it rejects
// tst.w/subq.w/cmp.w/dbra.) See OPNOTE in README.
__attribute__((optnone))
void show_version_alert(const char *p, int len) {
    if (len < 0) len = 0;
    if (len > 255) len = 255;
    unsigned char *d = pstr;
    *d++ = (unsigned char)len;
    while (len-- > 0) *d++ = (unsigned char)*p++;

    initgraf(QD_THEPORT);
    initfonts();
    initwindows();
    initmenus();
    teinit();
    initdialogs(0);
    initcursor();

    // Populate the menu bar (dummy Apple + File + Edit menus) so it looks like a
    // real app. Edit gets no items (no AppendMenu) — we only need the titles for
    // the screenshot, and AppendMenu with an empty string corrupts the menu.
    void *m;
    m = newmenu(1, menu_apple_title); appendmenu(m, menu_apple_items); insertmenu(m, 0);
    m = newmenu(2, menu_file_title);  appendmenu(m, menu_file_items);  insertmenu(m, 0);
    m = newmenu(3, menu_edit_title);                                   insertmenu(m, 0);
    drawmenubar();

    paramtext(pstr, empty_pstr, empty_pstr, empty_pstr);
    (void)notealert(128, 0);
    exit_to_shell();
}

// --- Embedded-Swift runtime stubs -------------------------------------------
// With no stdlib, LLVM's codegen and Swift's runtime can reference a handful of
// C symbols. Provide 68000-safe implementations. (Milestone 1 builds with
// -no-allocations, so the heap entry points should never be reached.)

// LLVM may emit these for struct copies / zero-init. Hand-rolled so we never
// pull in a compiler-rt built for 68020+. optnone for the same reason as
// show_version_alert: keep the byte loops off the scaled-index addressing mode.
__attribute__((optnone))
void *memset(void *dest, int c, unsigned long n) {
    unsigned char *p = (unsigned char *)dest;
    for (unsigned long i = 0; i < n; i++) p[i] = (unsigned char)c;
    return dest;
}
__attribute__((optnone))
void *memcpy(void *dest, const void *src, unsigned long n) {
    unsigned char *d = (unsigned char *)dest;
    const unsigned char *s = (const unsigned char *)src;
    for (unsigned long i = 0; i < n; i++) d[i] = s[i];
    return dest;
}
__attribute__((optnone))
void *memmove(void *dest, const void *src, unsigned long n) {
    unsigned char *d = (unsigned char *)dest;
    const unsigned char *s = (const unsigned char *)src;
    if (d < s) {
        for (unsigned long i = 0; i < n; i++) d[i] = s[i];
    } else {
        for (unsigned long i = n; i > 0; i--) d[i - 1] = s[i - 1];
    }
    return dest;
}

// The 68000 has no CAS; Swift IRGen can still emit __sync_* builtins. A GEMDOS-
// style single-threaded app makes non-atomic implementations safe. Use asm
// names to bypass clang's builtin shadowing.
int __sync_val_compare_and_swap_4_impl(volatile int *ptr, int oldv, int newv)
    __asm__("__sync_val_compare_and_swap_4");
int __sync_val_compare_and_swap_4_impl(volatile int *ptr, int oldv, int newv) {
    int cur = *ptr;
    if (cur == oldv) *ptr = newv;
    return cur;
}
int __sync_fetch_and_add_4_impl(volatile int *ptr, int v) __asm__("__sync_fetch_and_add_4");
int __sync_fetch_and_add_4_impl(volatile int *ptr, int v) {
    int old = *ptr; *ptr = old + v; return old;
}
int __sync_fetch_and_sub_4_impl(volatile int *ptr, int v) __asm__("__sync_fetch_and_sub_4");
int __sync_fetch_and_sub_4_impl(volatile int *ptr, int v) {
    int old = *ptr; *ptr = old - v; return old;
}

// Swift's trap/fatalError path may reference abort(). Bail out to the Finder.
__attribute__((noreturn))
void abort(void) { exit_to_shell(); }

// Embedded Swift's runtime references the heap entry points even when nothing
// is allocated. Milestone 1 never allocates, so reaching posix_memalign means
// dead-stripping missed a metadata path -> fail loud. free is a no-op.
int posix_memalign(void **out, unsigned long align, unsigned long size) {
    (void)out; (void)align; (void)size;
    exit_to_shell();
}
void free(void *p) { (void)p; }
