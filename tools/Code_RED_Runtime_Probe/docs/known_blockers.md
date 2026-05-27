# Known Blockers

- Current region/sector, save/load state, session/network state, and script count do not have confirmed safe ScriptHook native wrappers in this pass.
- `UI_SEND_EVENT` exists, but the exact event payload expectations are still uncertain. It is disabled by default.
- Sector enable/disable calls can prove runtime behavior only after single-player has loaded enough world state.
- This probe cannot prove whether MP backend scripts work because it intentionally does not launch them.
