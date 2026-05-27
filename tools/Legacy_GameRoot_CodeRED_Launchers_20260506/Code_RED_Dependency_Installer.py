from __future__ import annotations
            import subprocess
            import sys
            from pathlib import Path

            ROOT = Path(__file__).resolve().parent
            REQUIREMENTS = ROOT / 'Code_RED' / 'requirements.txt'
            CORE_PACKAGES = ['pillow', 'cryptography', 'numpy', 'matplotlib']

            def run(cmd: list[str]) -> int:
                print('> ' + ' '.join(cmd))
                return subprocess.call(cmd)

            def main() -> int:
                python = sys.executable or 'python'
                code = run([python, '-m', 'pip', 'install', '--upgrade', 'pip'])
                if code:
                    return code
                if REQUIREMENTS.exists():
                    code = run([python, '-m', 'pip', 'install', '-r', str(REQUIREMENTS)])
                else:
                    code = run([python, '-m', 'pip', 'install', *CORE_PACKAGES])
                print('
External components are not bundled here.')
                print('- ScriptHookRDR: recommended baseline when you want the simpler hook route.')
                print('- RedHook: advanced optional route for the generated .red bridge plugin scaffold.')
                print('- Do not assume both hook stacks should be active together; test one strategy at a time.')
                print('- Visual Studio Build Tools 2022 x64 are recommended only if you compile the C++ or C# launcher sources.')
                return code

            if __name__ == '__main__':
                raise SystemExit(main())
