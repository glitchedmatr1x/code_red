# Code RED MP Freeroam Pass 3 Known Risks

- If there is no behavior change, the redirected `trafficDebugThread` launch slot may not be reached at runtime.
- If the game crashes when the script starts, the bootstrap likely fired but the restored MP backend script format/path/resource wrapper is wrong.
- If loading starts and hangs, the backend likely starts partially and the next blocker is session or game state.
- Magic RDR import/export verification is required before launch.  If Magic RDR does not encode/import decoded `.sc.xml` resources correctly, use the existing Pass 5 RPF as the base and import only the Pass 2 WSC files.
- Donor CSC/XSC files are included as raw variants only.  XSC/CSC-to-PC-WSC conversion remains blocked until the wrapper/compression lane is proven.
- The bootstrap path is a same-size replacement of an existing script path, not a new bytecode launch block.
