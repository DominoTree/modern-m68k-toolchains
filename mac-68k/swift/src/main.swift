// Swift "hello" for the original Macintosh System 1.0 (Mac 128K, MC68000).
//
// Milestone 2: open a modal NoteAlert dialog showing the Swift + LLVM versions
// used to build it, then return to the Finder — the visible analogue of
// the Atari TOS port's form_alert demo. The Toolbox trap glue (QuickDraw/Dialog init,
// ParamText, NoteAlert) lives in mactraps.c.
//
// The message is handed to the C side via StaticString.withUTF8Buffer rather
// than by taking the address of the StaticString, which came out ~15 bytes off
// in testing. The exact cause wasn't bisected on the Mac: the Atari port hit a
// similar symptom from a real linker/toslink section gap, but this pipeline is
// one contiguous section (app.ld) with no relocation step, so that mechanism
// shouldn't apply. withUTF8Buffer is a robust way to pass the bytes regardless.
//
// Embedded Swift mode, no stdlib runtime.

@_silgen_name("show_version_alert")
func showVersionAlert(_ text: UnsafePointer<CChar>, _ len: Int32)

@_silgen_name("exit_to_shell")
func exitToShell() -> Never

// Three lines, like the Atari TOS port. Classic Mac text breaks on carriage
// return (\r = 0x0D), not newline; the Dialog Manager honors it in static text.
let VERSION: StaticString = "Built with:\rSwift 6.3.2\rLLVM 21.1.6"

@_cdecl("_start")
public func swiftMain() {
    VERSION.withUTF8Buffer { buf in
        showVersionAlert(
            UnsafeRawPointer(buf.baseAddress!).assumingMemoryBound(to: CChar.self),
            Int32(buf.count))
    }
    exitToShell()
}
