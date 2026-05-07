using System;
using System.Diagnostics;
using System.IO;

class CodeRedLauncher
{
    static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string bridgeDir = Path.Combine(root, "Code_RED_Launch");
        string target = "PlayRDR.exe";
        if (args.Length > 0 && string.Equals(args[0], "play", StringComparison.OrdinalIgnoreCase)) target = "PlayRDR.exe";
        if (args.Length > 0 && string.Equals(args[0], "direct", StringComparison.OrdinalIgnoreCase)) target = "RDR.exe";
        string targetPath = Path.Combine(root, target);
        if (!File.Exists(targetPath))
        {
            Console.WriteLine("Target executable not found: " + targetPath);
            return 1;
        }
        var psi = new ProcessStartInfo(targetPath)
        {
            WorkingDirectory = root,
            UseShellExecute = false,
        };
        psi.EnvironmentVariables["CODERED_BRIDGE_DIR"] = bridgeDir;
        psi.EnvironmentVariables["CODERED_ACTIVE_SESSION"] = Path.Combine(bridgeDir, "active_session.json");
        psi.EnvironmentVariables["CODERED_LAUNCH_PLAN"] = Path.Combine(bridgeDir, "launch_plan.json");
        psi.EnvironmentVariables["CODERED_HOOK_BOOTSTRAP"] = Path.Combine(root, "Code_RED_HookBridge", "hook_bootstrap.json");
        psi.EnvironmentVariables["CODERED_HOOK_PACK_DIR"] = Path.Combine(root, "Code_RED_HookBridge");
        Process.Start(psi);
        return 0;
    }
}
