// Swift hello-world for EmuTOS / Atari TOS that opens a GEM form_alert
// dialog showing the Swift + LLVM versions, exits via GEMDOS Pterm0.
// Embedded Swift mode, no stdlib runtime. m68k trap glue lives in gemdos.c.

@_silgen_name("appl_init")  func appl_init() -> Int16
@_silgen_name("appl_exit")  func appl_exit() -> Int16
@_silgen_name("form_alert") func form_alert(_ defaultButton: Int16, _ text: UnsafePointer<CChar>) -> Int16
@_silgen_name("pterm0")     func pterm0() -> Never

// form_alert grammar: `[icon][line1|line2|...][btn1|btn2|...]`.
let ALERT_TEXT: StaticString = "[1][Built with:|Swift 6.3.2|LLVM 21.1.6][ OK ]"

@_cdecl("_start")
public func swift_main() {
    let id = appl_init()
    if id != -1 {
        _ = form_alert(1, UnsafeRawPointer(ALERT_TEXT.utf8Start).assumingMemoryBound(to: CChar.self))
        _ = appl_exit()
    }
    pterm0()
}
