using System;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace FtpBackend
{
    internal sealed class Settings
    {
        public string Ip = "0.0.0.0";
        public int Port = 21;
        public string User = "admin";
        public string Password = string.Empty;
        public bool AnyLogin;
        public string Target;
        public string LineId = "00001";
        public bool Dedup = true;
        public int DedupMinutes;
        public bool KeepDuplicates;
        public int PassiveMin = 50000;
        public int PassiveMax = 50100;
        public int IdleTimeout = 600;
        public int DataTimeout = 60;
        public bool ShowHelp;
    }

    internal static class Program
    {
        public const string Version = "1.0.0";
        public const string PasswordEnvironmentVariable = "FTPBRIDGE_PASSWORD";

        private const string Usage =
            "FtpBackend " + Version + " - FTP server penerima foto + rename otomatis\n" +
            "\n" +
            "  --ip <alamat>            IP yang didengarkan (default 0.0.0.0 = semua)\n" +
            "  --port <n>               Port FTP (default 21)\n" +
            "  --user <nama>            Username FTP (default admin)\n" +
            "  --password <sandi>       Password FTP (atau env " + PasswordEnvironmentVariable + ")\n" +
            "  --any-login              Terima username/password apa saja\n" +
            "  --target <folder>        Folder penyimpanan foto (wajib)\n" +
            "  --line-id <id>           LINE-ID untuk nama file (default 00001)\n" +
            "  --no-dedup               Simpan semua foto walau code sama\n" +
            "  --dedup-minutes <n>      Rentang duplikat dalam menit (0 = selamanya)\n" +
            "  --keep-duplicates        Simpan duplikat ke subfolder _duplikat\n" +
            "  --pasv-min <n>           Port pasif minimum (0 = otomatis)\n" +
            "  --pasv-max <n>           Port pasif maksimum\n" +
            "\n" +
            "Perintah via stdin: STOP | SET LINEID <id> | PING\n";

        private static int Main(string[] args)
        {
            EventSink.Init();
            AppDomain.CurrentDomain.UnhandledException += (sender, e) =>
                EventSink.Log("error", "Kesalahan tak terduga: " + e.ExceptionObject);
            TaskScheduler.UnobservedTaskException += (sender, e) => e.SetObserved();

            int workers, io;
            ThreadPool.GetMinThreads(out workers, out io);
            ThreadPool.SetMinThreads(Math.Max(workers, 32), Math.Max(io, 32));

            Settings settings;
            string error;
            if (!TryParseArgs(args, out settings, out error))
            {
                return Fail(error);
            }
            if (settings.ShowHelp)
            {
                Console.Error.Write(Usage);
                return 0;
            }

            IPAddress bindAddress;
            if (!IPAddress.TryParse(settings.Ip, out bindAddress))
            {
                return Fail("Alamat IP tidak valid: " + settings.Ip);
            }
            if (settings.Port < 1 || settings.Port > 65535)
            {
                return Fail("Port harus 1-65535");
            }
            if (string.IsNullOrEmpty(settings.Target))
            {
                return Fail("Folder tujuan (--target) wajib diisi");
            }
            string lineId = PhotoProcessor.CleanLineId(settings.LineId ?? string.Empty);
            if (lineId.Length == 0)
            {
                return Fail("LINE-ID tidak boleh kosong");
            }

            var processor = new PhotoProcessor(settings.Target, lineId, settings.Dedup, settings.DedupMinutes, settings.KeepDuplicates);
            int knownCodes;
            try
            {
                knownCodes = processor.Prepare();
            }
            catch (Exception ex)
            {
                return Fail("Folder tujuan tidak bisa dipakai: " + ex.Message);
            }

            var options = new ServerOptions();
            options.BindAddress = bindAddress;
            options.Port = settings.Port;
            options.User = settings.User ?? string.Empty;
            options.Password = settings.Password ?? string.Empty;
            options.AllowAnyLogin = settings.AnyLogin;
            options.PassivePortMin = settings.PassiveMin;
            options.PassivePortMax = settings.PassiveMax;
            options.IdleTimeoutSeconds = Math.Max(30, settings.IdleTimeout);
            options.DataTimeoutSeconds = Math.Max(5, settings.DataTimeout);

            var server = new FtpServer(options, processor);
            try
            {
                server.Start();
            }
            catch (SocketException ex)
            {
                return Fail(DescribeBindError(ex, settings));
            }

            EventSink.Emit("state", "state", "listening", "ip", settings.Ip, "port", settings.Port,
                "target", processor.TargetDir, "line_id", lineId, "known_codes", knownCodes, "version", Version);
            EventSink.Log("info", string.Format(CultureInfo.InvariantCulture,
                "Server FTP aktif di {0}:{1}, folder tujuan {2}", settings.Ip, settings.Port, processor.TargetDir));
            if (settings.Dedup)
            {
                EventSink.Log("info", knownCodes + " code sudah ada di folder tujuan (dipakai untuk cek duplikat)");
            }

            RunCommandLoop(processor);

            EventSink.Log("info", "Menghentikan server...");
            server.Stop();
            EventSink.Emit("state", "state", "stopped");
            return 0;
        }

        /// <summary>Reads control commands from the GUI. Returns on STOP or when stdin closes.</summary>
        private static void RunCommandLoop(PhotoProcessor processor)
        {
            var input = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false));
            string line;
            while ((line = input.ReadLine()) != null)
            {
                line = line.Trim();
                if (line.Equals("STOP", StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
                if (line.Equals("PING", StringComparison.OrdinalIgnoreCase))
                {
                    EventSink.Emit("pong");
                    continue;
                }
                if (line.StartsWith("SET LINEID ", StringComparison.OrdinalIgnoreCase))
                {
                    string value = PhotoProcessor.CleanLineId(line.Substring("SET LINEID ".Length));
                    if (value.Length == 0)
                    {
                        EventSink.Log("warn", "LINE-ID kosong diabaikan");
                        continue;
                    }
                    processor.LineId = value;
                    EventSink.Emit("line_id", "line_id", value);
                    EventSink.Log("info", "LINE-ID sekarang: " + value);
                    continue;
                }
                if (line.Length > 0)
                {
                    EventSink.Log("warn", "Perintah tidak dikenal: " + line);
                }
            }
        }

        private static bool TryParseArgs(string[] args, out Settings settings, out string error)
        {
            settings = new Settings();
            error = null;
            string envPassword = Environment.GetEnvironmentVariable(PasswordEnvironmentVariable);
            if (envPassword != null)
            {
                settings.Password = envPassword;
            }

            try
            {
                for (int i = 0; i < args.Length; i++)
                {
                    switch (args[i].ToLowerInvariant())
                    {
                        case "--ip": settings.Ip = Next(args, ref i); break;
                        case "--port": settings.Port = NextInt(args, ref i); break;
                        case "--user": settings.User = Next(args, ref i); break;
                        case "--password": settings.Password = Next(args, ref i); break;
                        case "--any-login": settings.AnyLogin = true; break;
                        case "--target": settings.Target = Next(args, ref i); break;
                        case "--line-id": settings.LineId = Next(args, ref i); break;
                        case "--no-dedup": settings.Dedup = false; break;
                        case "--dedup-minutes": settings.DedupMinutes = NextInt(args, ref i); break;
                        case "--keep-duplicates": settings.KeepDuplicates = true; break;
                        case "--pasv-min": settings.PassiveMin = NextInt(args, ref i); break;
                        case "--pasv-max": settings.PassiveMax = NextInt(args, ref i); break;
                        case "--idle-timeout": settings.IdleTimeout = NextInt(args, ref i); break;
                        case "--data-timeout": settings.DataTimeout = NextInt(args, ref i); break;
                        case "-h":
                        case "--help":
                        case "/?":
                            settings.ShowHelp = true;
                            break;
                        default:
                            error = "Argumen tidak dikenal: " + args[i];
                            return false;
                    }
                }
            }
            catch (ArgumentException ex)
            {
                error = ex.Message;
                return false;
            }
            return true;
        }

        private static string Next(string[] args, ref int i)
        {
            if (i + 1 >= args.Length)
            {
                throw new ArgumentException("Nilai untuk " + args[i] + " belum diisi");
            }
            i++;
            return args[i];
        }

        private static int NextInt(string[] args, ref int i)
        {
            string name = args[i];
            string value = Next(args, ref i);
            int result;
            if (!int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out result))
            {
                throw new ArgumentException("Nilai " + name + " harus angka: " + value);
            }
            return result;
        }

        private static string DescribeBindError(SocketException ex, Settings settings)
        {
            string where = settings.Ip + ":" + settings.Port.ToString(CultureInfo.InvariantCulture);
            switch (ex.SocketErrorCode)
            {
                case SocketError.AddressAlreadyInUse:
                    return "Port " + where + " sudah dipakai aplikasi lain (mis. FTP server lain / IIS). Ganti port atau tutup aplikasi tersebut.";
                case SocketError.AddressNotAvailable:
                    return "IP " + settings.Ip + " bukan milik komputer ini. Pilih IP lain atau 0.0.0.0.";
                case SocketError.AccessDenied:
                    return "Akses ke port " + where + " ditolak. Coba port lain atau jalankan sebagai Administrator.";
                default:
                    return "Tidak bisa membuka " + where + ": " + ex.Message;
            }
        }

        private static int Fail(string message)
        {
            EventSink.Emit("state", "state", "error", "message", message);
            return 2;
        }
    }
}
