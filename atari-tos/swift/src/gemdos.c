// GEMDOS + AES m68k trap wrappers. Inline asm tricks live in C so the Swift
// side can stay portable. clang m68k accepts these via LLVM 21 + our patches.
//
// Calling conventions:
//   GEMDOS (trap #1) — pop function word + args from user stack
//   AES    (trap #2) — d0 = 0xC8, d1 = &aes_pb

#include <stdint.h>

typedef struct {
    uint16_t opcode;
    uint16_t n_int_in;
    uint16_t n_int_out;
    uint16_t n_addr_in;
    uint16_t n_addr_out;
} AesControl;

typedef struct {
    uint16_t version;
    uint16_t app_max;
    uint16_t app_id;
    uint32_t user;
    const void *rsc;
    uint32_t reserved[4];
} AesGlobal;

typedef struct {
    AesControl *control;
    AesGlobal *global;
    const int16_t *int_in;
    int16_t *int_out;
    const void **addr_in;
    void **addr_out;
} AesPb;

static AesGlobal aes_global = {0};

__attribute__((noinline))
void cconws(const char *s) {
    __asm__ volatile (
        "move.l %0, -(%%sp)\n\t"
        "move.w #9, -(%%sp)\n\t"
        "trap #1\n\t"
        "lea 6(%%sp), %%sp\n\t"
        :
        : "r"(s)
        : "memory", "d0", "d1", "d2"
    );
}

__attribute__((noinline, noreturn))
void pterm0(void) {
    __asm__ volatile (
        "move.w #0, -(%%sp)\n\t"
        "trap #1\n\t"
        ::: "memory"
    );
    __builtin_unreachable();
}

__attribute__((noinline))
static void aes_trap(const AesPb *pb) {
    __asm__ volatile (
        "move.l %0, %%d1\n\t"
        "move.w #0xc8, %%d0\n\t"
        "trap #2\n\t"
        :
        : "r"(pb)
        : "memory", "d0", "d1", "d2", "a0", "a1", "a2"
    );
}

__attribute__((noinline))
int16_t aes_call(uint16_t opcode,
                 const int16_t *int_in, uint16_t n_int_in,
                 const void **addr_in, uint16_t n_addr_in) {
    AesControl control = {opcode, n_int_in, 1, n_addr_in, 0};
    int16_t int_out[7] = {0};
    void *addr_out[1] = {0};

    AesPb pb = {
        .control = &control,
        .global = &aes_global,
        .int_in = n_int_in ? int_in : 0,
        .int_out = int_out,
        .addr_in = n_addr_in ? addr_in : 0,
        .addr_out = addr_out,
    };

    aes_trap(&pb);
    return int_out[0];
}

int16_t appl_init(void)  { return aes_call(10, 0, 0, 0, 0); }
int16_t appl_exit(void)  { return aes_call(19, 0, 0, 0, 0); }

int16_t form_alert(int16_t default_button, const char *text) {
    int16_t ii[1] = {default_button};
    const void *ai[1] = {text};
    return aes_call(52, ii, 1, ai, 1);
}

// LLVM may emit memset for struct zero-init. compiler_rt for embedded m68k
// would use 68020+ insns; provide our own 68000-safe version.
void *memset(void *dest, int c, unsigned long n) {
    unsigned char *p = (unsigned char *)dest;
    for (unsigned long i = 0; i < n; i++) p[i] = (unsigned char)c;
    return dest;
}

// abort() may be referenced by Swift's panic path.
__attribute__((noreturn))
void abort(void) { pterm0(); }

// Swift IRGen on m68k emits sync builtins for atomic ops. 68000 has no native
// atomics; in single-threaded GEMDOS app these are safe to non-atomically stub.
// Use asm-name to bypass clang's builtin shadowing.
int __sync_val_compare_and_swap_4_impl(volatile int *ptr, int oldv, int newv) __asm__("__sync_val_compare_and_swap_4");
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

// Heap stubs. Embedded Swift shouldn't allocate in our hello-world; if reached
// it means dead-stripping missed a class metadata path — fail loud.
int posix_memalign(void **out, unsigned long align, unsigned long size) {
    (void)out; (void)align; (void)size;
    pterm0();
}
void free(void *p) { (void)p; }

