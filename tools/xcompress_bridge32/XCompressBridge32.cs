using System;
using System.IO;
using System.Runtime.InteropServices;

internal static class XCompressBridge32
{
    private const int XMEMCODEC_LZX = 1;

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemCreateDecompressionContext(int codecType, int codecParams, int flags, ref int context);

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemDestroyDecompressionContext(int context);

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemResetDecompressionContext(int context);

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemDecompress(int context, byte[] destination, ref int destSize, byte[] source, int srcSize);

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemCreateCompressionContext(int codecType, int codecParams, int flags, ref int context);

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemDestroyCompressionContext(int context);

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemResetCompressionContext(int context);

    [DllImport("xcompress32.dll", CallingConvention = CallingConvention.Winapi)]
    private static extern int XMemCompress(int context, byte[] destination, ref int destSize, byte[] source, int srcSize);

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length < 1)
            {
                Usage();
                return 2;
            }

            string command = args[0].ToLowerInvariant();
            if (command == "decompress")
            {
                if (args.Length < 4)
                {
                    Usage();
                    return 2;
                }
                return Decompress(args[1], args[2], ParsePositiveInt(args[3], "expected_size"), ParseSkip(args));
            }
            if (command == "compress")
            {
                if (args.Length < 3)
                {
                    Usage();
                    return 2;
                }
                return Compress(args[1], args[2]);
            }
            if (command == "roundtrip")
            {
                if (args.Length < 3)
                {
                    Usage();
                    return 2;
                }
                return RoundTrip(args[1], args[2]);
            }

            Usage();
            return 2;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(JsonStatus("exception", -1, 0, 0, Escape(ex.GetType().Name + ": " + ex.Message)));
            return 1;
        }
    }

    private static int Decompress(string inputPath, string outputPath, int expectedSize, int skip)
    {
        byte[] input = File.ReadAllBytes(inputPath);
        if (skip < 0 || skip > input.Length)
        {
            Console.Error.WriteLine(JsonStatus("bad_skip", -1, input.Length, 0, "skip outside input"));
            return 2;
        }

        byte[] source = new byte[input.Length - skip];
        Buffer.BlockCopy(input, skip, source, 0, source.Length);
        byte[] destination = new byte[expectedSize];
        int destSize = destination.Length;
        int context = 0;
        int hr = XMemCreateDecompressionContext(XMEMCODEC_LZX, 0, 0, ref context);
        if (hr != 0)
        {
            Console.Error.WriteLine(JsonStatus("create_decompression_failed", hr, source.Length, 0, ""));
            return 1;
        }

        try
        {
            hr = XMemDecompress(context, destination, ref destSize, source, source.Length);
        }
        finally
        {
            try { XMemResetDecompressionContext(context); } catch { }
            try { XMemDestroyDecompressionContext(context); } catch { }
        }

        if (hr != 0)
        {
            Console.Error.WriteLine(JsonStatus("decompress_failed", hr, source.Length, destSize, ""));
            return 1;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath)));
        using (FileStream stream = File.Create(outputPath))
        {
            stream.Write(destination, 0, destSize);
        }
        Console.WriteLine(JsonStatus("ok", hr, source.Length, destSize, ""));
        return 0;
    }

    private static int Compress(string inputPath, string outputPath)
    {
        byte[] source = File.ReadAllBytes(inputPath);
        byte[] destination = new byte[source.Length + 8192];
        int destSize = destination.Length;
        int context = 0;
        int hr = XMemCreateCompressionContext(XMEMCODEC_LZX, 0, 0, ref context);
        if (hr != 0)
        {
            Console.Error.WriteLine(JsonStatus("create_compression_failed", hr, source.Length, 0, ""));
            return 1;
        }

        try
        {
            hr = XMemCompress(context, destination, ref destSize, source, source.Length);
        }
        finally
        {
            try { XMemResetCompressionContext(context); } catch { }
            try { XMemDestroyCompressionContext(context); } catch { }
        }

        if (hr != 0)
        {
            Console.Error.WriteLine(JsonStatus("compress_failed", hr, source.Length, destSize, ""));
            return 1;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath)));
        using (FileStream stream = File.Create(outputPath))
        {
            stream.Write(destination, 0, destSize);
        }
        Console.WriteLine(JsonStatus("ok", hr, source.Length, destSize, ""));
        return 0;
    }

    private static int RoundTrip(string inputPath, string outputPath)
    {
        string temp = Path.Combine(Path.GetTempPath(), "codered_xcompress_" + Guid.NewGuid().ToString("N") + ".bin");
        try
        {
            int compressCode = Compress(inputPath, temp);
            if (compressCode != 0)
            {
                return compressCode;
            }
            return Decompress(temp, outputPath, checked((int)new FileInfo(inputPath).Length), 0);
        }
        finally
        {
            try { if (File.Exists(temp)) File.Delete(temp); } catch { }
        }
    }

    private static int ParsePositiveInt(string value, string name)
    {
        int parsed;
        if (!int.TryParse(value, out parsed) || parsed <= 0)
        {
            throw new ArgumentException(name + " must be a positive integer");
        }
        return parsed;
    }

    private static int ParseSkip(string[] args)
    {
        for (int i = 4; i < args.Length; i++)
        {
            if (args[i] == "--skip" && i + 1 < args.Length)
            {
                return ParsePositiveOrZero(args[i + 1], "skip");
            }
        }
        return 0;
    }

    private static int ParsePositiveOrZero(string value, string name)
    {
        int parsed;
        if (!int.TryParse(value, out parsed) || parsed < 0)
        {
            throw new ArgumentException(name + " must be zero or a positive integer");
        }
        return parsed;
    }

    private static void Usage()
    {
        Console.Error.WriteLine("Usage:");
        Console.Error.WriteLine("  codered_xcompress_bridge32.exe decompress <input> <output> <expected_size> [--skip N]");
        Console.Error.WriteLine("  codered_xcompress_bridge32.exe compress <input> <output>");
        Console.Error.WriteLine("  codered_xcompress_bridge32.exe roundtrip <input> <output>");
    }

    private static string JsonStatus(string status, int hr, int inputSize, int outputSize, string message)
    {
        return "{\"status\":\"" + Escape(status) + "\",\"hr\":" + hr + ",\"input_size\":" + inputSize + ",\"output_size\":" + outputSize + ",\"message\":\"" + Escape(message) + "\"}";
    }

    private static string Escape(string value)
    {
        return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
    }
}
