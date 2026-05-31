// Rust hello-world for EmuTOS / Atari TOS that opens a GEM form_alert
// dialog instead of printing to the console. No C runtime, 
// every system call is inline m68k asm.
//
// Calling conventions used:
//   GEMDOS (trap #1) — pop function word + args from user stack
//   AES    (trap #2) — d0 = 0xC8, d1 = &aes_pb

#![no_std]
#![no_main]
#![feature(asm_experimental_arch)]

use core::arch::asm;
use core::cell::UnsafeCell;
use core::panic::PanicInfo;
use core::ptr;

// form_alert grammar: `[icon][line1|line2|...][btn1|btn2|...]`.
// Icons: 0=none, 1=note, 2=question, 3=stop.
// Version strings come from build.rs (host `rustc -vV`).
static ALERT_TEXT: &[u8] = concat!(
    "[1][Built with:|",
    env!("BUILD_RUSTC"),
    "|",
    env!("BUILD_LLVM"),
    "][ OK ]\0",
)
.as_bytes();

// ---------- AES parameter block (XGEMDOS opcode 0xC8, trap #2) ----------

#[repr(C)]
struct AesControl {
    opcode: u16,
    n_int_in: u16,
    n_int_out: u16,
    n_addr_in: u16,
    n_addr_out: u16,
}

#[repr(C)]
struct AesGlobal {
    version: u16,
    app_max: u16,
    app_id: u16,
    user: u32,
    rsc: *const u8,
    reserved: [u32; 4],
}

#[repr(C)]
struct AesPb {
    control: *mut AesControl,
    global: *mut AesGlobal,
    int_in: *const i16,
    int_out: *mut i16,
    addr_in: *const *const u8,
    addr_out: *mut *mut u8,
}

// AES populates app_id in `global` at appl_init and references it on later
// calls — must persist across the whole app lifetime.
struct GlobalCell(UnsafeCell<AesGlobal>);
unsafe impl Sync for GlobalCell {}

static GLOBAL: GlobalCell = GlobalCell(UnsafeCell::new(AesGlobal {
    version: 0,
    app_max: 0,
    app_id: 0,
    user: 0,
    rsc: ptr::null(),
    reserved: [0; 4],
}));

unsafe fn aes_trap(pb: *const AesPb) {
    asm!(
        "move.l {pb},%d1",
        "move.w #0xc8,%d0",
        "trap #2",
        pb = in(reg) pb,
        out("d0") _,
        out("d1") _,
        out("d2") _,
        out("a0") _,
        out("a1") _,
        out("a2") _,
    );
}

// Build a parameter block on the stack and dispatch. int_out[0] is the
// implicit AES return code; declared int_out params start at index 1. 7 is
// the AES per-call maximum.
unsafe fn aes_call(
    opcode: u16,
    int_in: &[i16],
    addr_in: &[*const u8],
) -> i16 {
    let mut control = AesControl {
        opcode,
        n_int_in: int_in.len() as u16,
        n_int_out: 1,
        n_addr_in: addr_in.len() as u16,
        n_addr_out: 0,
    };
    let mut int_out: [i16; 7] = [0; 7];
    let mut addr_out: [*mut u8; 1] = [ptr::null_mut()];

    let pb = AesPb {
        control: &mut control,
        global: GLOBAL.0.get(),
        int_in: if int_in.is_empty() { ptr::null() } else { int_in.as_ptr() },
        int_out: int_out.as_mut_ptr(),
        addr_in: if addr_in.is_empty() { ptr::null() } else { addr_in.as_ptr() },
        addr_out: addr_out.as_mut_ptr(),
    };

    aes_trap(&pb);
    int_out[0]
}

unsafe fn appl_init() -> i16 {
    aes_call(10, &[], &[])
}

unsafe fn appl_exit() -> i16 {
    aes_call(19, &[], &[])
}

// form_alert: int_in=[default_button], addr_in=[alert_string].
unsafe fn form_alert(default_button: i16, text: *const u8) -> i16 {
    let int_in = [default_button];
    let addr_in = [text];
    aes_call(52, &int_in, &addr_in)
}

// ---------- Entry point ----------

#[no_mangle]
#[link_section = ".text._start"]
pub unsafe extern "C" fn _start() -> ! {
    let ap_id = appl_init();
    if ap_id != -1 {
        let _ = form_alert(1, ALERT_TEXT.as_ptr());
        let _ = appl_exit();
    }
    pterm0();
}

// GEMDOS Pterm0 (trap #1, function 0): clean process exit.
unsafe fn pterm0() -> ! {
    asm!(
        "move.w #0,-(%sp)",
        "trap #1",
        options(noreturn),
    );
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    unsafe { pterm0() }
}

// LLVM may emit calls to `abort` along the panic path. Resolve to Pterm0
// so the program exits cleanly instead of jumping to address 0.
#[no_mangle]
unsafe extern "C" fn abort() -> ! {
    pterm0()
}

// LLVM lowers struct zero-init to a `memset` call. compiler_builtins ships
// a memset shim behind the `mem` feature, but its thunk uses `bra.l`,
// a 68020+ instruction unavailable on 68000. Provide our own.
#[no_mangle]
unsafe extern "C" fn memset(dest: *mut u8, c: i32, n: usize) -> *mut u8 {
    let mut i = 0;
    while i < n {
        *dest.add(i) = c as u8;
        i += 1;
    }
    dest
}
