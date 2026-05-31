// Zig hello-world for EmuTOS / Atari TOS that opens a GEM form_alert
// dialog instead of printing to the console. No std lib, every system
// call is inline m68k asm.
//
// Calling conventions used:
//   GEMDOS (trap #1) — pop function word + args from user stack
//   AES    (trap #2) — d0 = 0xC8, d1 = &aes_pb
const std = @import("std");
const builtin = @import("builtin");
const build_info = @import("build_info.zig");

// form_alert grammar: `[icon][line1|line2|...][btn1|btn2|...]`.
// Icons: 0=none, 1=note, 2=question, 3=stop.
const ALERT_TEXT: [*:0]const u8 = "[1][Built with:|zig " ++
    builtin.zig_version_string ++ "|" ++ build_info.llvm_version ++ "][ OK ]";

// ---------- AES parameter block (XGEMDOS opcode 0xC8, trap #2) ----------

const AesControl = extern struct {
    opcode: u16,
    n_int_in: u16,
    n_int_out: u16,
    n_addr_in: u16,
    n_addr_out: u16,
};

const AesGlobal = extern struct {
    version: u16,
    app_max: u16,
    app_id: u16,
    user: u32,
    rsc: ?[*]const u8,
    reserved: [4]u32,
};

const AesPb = extern struct {
    control: *AesControl,
    global: *AesGlobal,
    int_in: ?[*]const i16,
    int_out: [*]i16,
    addr_in: ?[*]const ?[*]const u8,
    addr_out: [*]?[*]u8,
};

// AES populates app_id in `global` at appl_init and references it on later
// calls — must persist across the whole app lifetime.
var GLOBAL: AesGlobal = .{
    .version = 0,
    .app_max = 0,
    .app_id = 0,
    .user = 0,
    .rsc = null,
    .reserved = .{ 0, 0, 0, 0 },
};

fn aes_trap(pb: *const AesPb) void {
    asm volatile (
        \\move.l %[pb], %%d1
        \\move.w #0xc8, %%d0
        \\trap #2
        :
        : [pb] "r" (pb),
        : .{ .memory = true });
}

// Build a parameter block on the stack and dispatch. int_out[0] is the
// implicit AES return code; declared int_out params start at index 1. 7 is
// the AES per-call maximum.
fn aes_call(
    opcode: u16,
    int_in: []const i16,
    addr_in: []const ?[*]const u8,
) i16 {
    var control: AesControl = .{
        .opcode = opcode,
        .n_int_in = @intCast(int_in.len),
        .n_int_out = 1,
        .n_addr_in = @intCast(addr_in.len),
        .n_addr_out = 0,
    };
    var int_out: [7]i16 = .{ 0, 0, 0, 0, 0, 0, 0 };
    var addr_out: [1]?[*]u8 = .{null};

    const pb: AesPb = .{
        .control = &control,
        .global = &GLOBAL,
        .int_in = if (int_in.len == 0) null else int_in.ptr,
        .int_out = &int_out,
        .addr_in = if (addr_in.len == 0) null else addr_in.ptr,
        .addr_out = &addr_out,
    };

    aes_trap(&pb);
    return int_out[0];
}

fn appl_init() i16 {
    return aes_call(10, &.{}, &.{});
}

fn appl_exit() i16 {
    return aes_call(19, &.{}, &.{});
}

// form_alert: int_in=[default_button], addr_in=[alert_string].
fn form_alert(default_button: i16, text: [*:0]const u8) i16 {
    const int_in = [_]i16{default_button};
    const addr_in = [_]?[*]const u8{@ptrCast(text)};
    return aes_call(52, &int_in, &addr_in);
}

// ---------- Entry point ----------

export fn _start() callconv(.c) noreturn {
    const ap_id = appl_init();
    if (ap_id != -1) {
        _ = form_alert(1, ALERT_TEXT);
        _ = appl_exit();
    }
    pterm0();
}

// GEMDOS Pterm0 (trap #1, function 0): clean process exit.
fn pterm0() noreturn {
    asm volatile (
        \\move.w #0, -(%%sp)
        \\trap #1
        ::: .{ .memory = true });
    unreachable;
}

// LLVM may emit calls to abort() along the panic path. Resolve cleanly.
export fn abort() noreturn {
    pterm0();
}

// LLVM lowers struct zero-init to memset. compiler_rt's memset thunk uses
// 68020+ insns we can't run on 68000, so provide our own.
export fn memset(dest: [*]u8, c: i32, n: usize) [*]u8 {
    var i: usize = 0;
    const byte: u8 = @truncate(@as(u32, @bitCast(c)));
    while (i < n) : (i += 1) dest[i] = byte;
    return dest;
}

pub const panic = std.debug.FullPanic(panicImpl);
fn panicImpl(_: []const u8, _: ?usize) noreturn {
    abort();
}
