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
        public bool KeepUnmatched;
        public int PassiveMin = 50000;
        public int PassiveMax = 50100;
        public int IdleTimeout = 600;
        public int DataTimeout = 60;
        public bool ShowHelp;

        // Client mode
        public string Mode = "server";
        public string RemoteDir = "/";
        public bool Recursive;
        public int MaxDepth = 10;
        public int Interval = 5;
        public int Workers = 3;
        public bool DeleteAfter;
        public string Extensions = "jpg,jpeg,png,bmp";
    }

    internal static class Program
    {
        public const string Version = "1.0.0";
        public const string PasswordEnvironmentVariable = "FTPBRIDGE_PASSWORD";

        private const string Usage =
            "FtpBackend " + Version + " - terima foto via FTP + rename otomatis\n" +
            "\n" +
            "  --mode server|client     server: kamera mengirim ke sini (default)\n" +
            "                           client: ambil foto dari server FTP lain\n" +
            "  --ip <alamat>            server: IP yang didengarkan (0.0.0.0 = semua)\n" +
            "                           client: IP/host server FTP tujuan\n" +
            "  --port <n>               Port FTP (default 21)\n" +
            "  --user <nama>            Username FTP (default admin)\n" +
            "  --password <sandi>       Password FTP (atau env " + PasswordEnvironmentVariable + ")\n" +
            "  --any-login              Terima username/password apa saja\n" +
            "  --target <folder>        Folder penyimpanan foto (wajib)\n" +
            "  --line-id <id>           LINE-ID untuk nama file (default 00001)\n" +
            "  --no-dedup               Simpan semua foto walau code sama\n" +
            "  --dedup-minutes <n>      Rentang duplikat dalam menit (0 = selamanya)\n" +
            "  --keep-duplicates        Simpan duplikat ke subfolder _duplikat\n" +
            "  --keep-unmatched         Simpan foto yang formatnya tidak sesuai ke _tidak_sesuai\n" +
            "                           (default: tidak disimpan, hanya dicatat di _log\\*.txt)\n" +
            "  --pasv-min <n>           Port pasif minimum (0 = otomatis)\n" +
            "  --pasv-max <n>           Port pasif maksimum\n" +
            "\n" +
            "Mode client:\n" +
            "  --remote-dir <folder>    Folder di server FTP (default /)\n" +
            "  --recursive              Ikut cek subfolder\n" +
            "  --interval <detik>       Jeda cek file baru (default 5)\n" +
            "  --workers <n>            Jumlah koneksi download paralel (default 3)\n" +
            "  --delete-after           Hapus file di server setelah berhasil diambil\n" +
            "  --extensions <daftar>    Ekstensi yang diambil (default jpg,jpeg,png,bmp)\n" +
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

            bool clientMode;
            if (settings.Mode.Equals("server", StringComparison.OrdinalIgnoreCase))
            {
                clientMode = false;
            }
            else if (settings.Mode.Equals("client", StringComparison.OrdinalIgnoreCase))
            {
                clientMode = true;
            }
            else
            {
                return Fail("Mode harus server atau client: " + settings.Mode);
            }

            IPAddress bindAddress = null;
            if (clientMode)
            {
                if (string.IsNullOrEmpty(settings.Ip) || settings.Ip.Trim().Length == 0)
                {
                    return Fail("Alamat server FTP belum diisi");
                }
            }
            else if (!IPAddress.TryParse(settings.Ip, out bindAddress))
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

            var processor = new PhotoProcessor(settings.Target, lineId, settings.Dedup, settings.DedupMinutes, settings.KeepDuplicates,
                settings.KeepUnmatched);
            int knownCodes;
            try
            {
                knownCodes = processor.Prepare();
            }
            catch (Exception ex)
            {
                return Fail("Folder tujuan tidak bisa dipakai: " + ex.Message);
            }

            EventSink.OpenDailyLogs(processor.LogDir);
            try
            {
                return clientMode
                    ? RunClient(settings, processor, lineId, knownCodes)
                    : RunServer(settings, bindAddress, processor, lineId, knownCodes);
            }
            finally
            {
                processor.CloseLogs();
                EventSink.CloseDailyLogs();
            }
        }

        private static int RunServer(Settings settings, IPAddress bindAddress, PhotoProcessor processor, string lineId, int knownCodes)
        {
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

            EventSink.Emit("state", "state", "listening", "mode", "server", "ip", settings.Ip, "port", settings.Port,
                "target", processor.TargetDir, "line_id", lineId, "known_codes", knownCodes, "version", Version);
            EventSink.Log("info", string.Format(CultureInfo.InvariantCulture,
                "Mode SERVER aktif di {0}:{1}, folder tujuan {2}", settings.Ip, settings.Port, processor.TargetDir));
            LogKnownCodes(settings, knownCodes);

            RunCommandLoop(processor);

            EventSink.Log("info", "Menghentikan server...");
            server.Stop();
            EventSink.Emit("state", "state", "stopped");
            return 0;
        }

        private static int RunClient(Settings settings, PhotoProcessor processor, string lineId, int knownCodes)
        {
            var options = new ClientOptions();
            options.Host = settings.Ip.Trim();
            options.Port = settings.Port;
            options.User = string.IsNullOrEmpty(settings.User) ? "anonymous" : settings.User;
            options.Password = settings.Password ?? string.Empty;
            options.RemoteDir = FtpPuller.NormalizeDir(settings.RemoteDir);
            options.Recursive = settings.Recursive;
            options.MaxDepth = Math.Max(0, settings.MaxDepth);
            options.IntervalSeconds = Math.Max(1, settings.Interval);
            options.Workers = Math.Min(16, Math.Max(1, settings.Workers));
            options.DeleteAfterDownload = settings.DeleteAfter;
            options.TimeoutSeconds = Math.Max(5, settings.DataTimeout);
            options.Extensions = (settings.Extensions ?? string.Empty).Split(new[] { ',', ';', ' ' }, StringSplitOptions.RemoveEmptyEntries);

            var puller = new FtpPuller(options, processor);
            string error = puller.Start();
            if (error != null)
            {
                return Fail(error);
            }

            EventSink.Emit("state", "state", "running", "mode", "client", "ip", options.Host, "port", options.Port,
                "target", processor.TargetDir, "line_id", lineId, "known_codes", knownCodes, "version", Version);
            EventSink.Log("info", string.Format(CultureInfo.InvariantCulture,
                "Mode CLIENT: cek {0}:{1}{2} setiap {3} detik ({4} koneksi download{5}{6}), folder tujuan {7}",
                options.Host, options.Port, options.RemoteDir, options.IntervalSeconds, options.Workers,
                options.Recursive ? ", termasuk subfolder" : string.Empty,
                options.DeleteAfterDownload ? ", hapus setelah diambil" : string.Empty,
                processor.TargetDir));
            LogKnownCodes(settings, knownCodes);

            RunCommandLoop(processor);

            EventSink.Log("info", "Menghentikan client...");
            puller.Stop();
            EventSink.Emit("state", "state", "stopped");
            return 0;
        }

        private static void LogKnownCodes(Settings settings, int knownCodes)
        {
            if (settings.Dedup)
            {
                EventSink.Log("info", knownCodes + " code sudah ada di folder tujuan (dipakai untuk cek duplikat)");
            }
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
                        case "--keep-unmatched": settings.KeepUnmatched = true; break;
                        case "--pasv-min": settings.PassiveMin = NextInt(args, ref i); break;
                        case "--pasv-max": settings.PassiveMax = NextInt(args, ref i); break;
                        case "--idle-timeout": settings.IdleTimeout = NextInt(args, ref i); break;
                        case "--data-timeout": settings.DataTimeout = NextInt(args, ref i); break;
                        case "--mode": settings.Mode = Next(args, ref i); break;
                        case "--remote-dir": settings.RemoteDir = Next(args, ref i); break;
                        case "--recursive": settings.Recursive = true; break;
                        case "--max-depth": settings.MaxDepth = NextInt(args, ref i); break;
                        case "--interval": settings.Interval = NextInt(args, ref i); break;
                        case "--workers": settings.Workers = NextInt(args, ref i); break;
                        case "--delete-after": settings.DeleteAfter = true; break;
                        case "--extensions": settings.Extensions = Next(args, ref i); break;
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
            EventSink.Log("error", message);
            EventSink.Emit("state", "state", "error", "message", message);
            return 2;
        }
    }
}
