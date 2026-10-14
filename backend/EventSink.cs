using System;
using System.Globalization;
using System.IO;
using System.Text;

namespace FtpBackend
{
    /// <summary>
    /// Writes one JSON object per line to stdout. The GUI reads these lines to
    /// follow what the backend is doing. Output is pure ASCII (non-ASCII is
    /// escaped as \uXXXX) so the console code page never matters.
    ///
    /// Log lines and received files are also kept in daily text files (the GUI only
    /// shows the newest ones): _log\log_yyyy-MM-dd.txt and _log\diterima_yyyy-MM-dd.txt.
    /// </summary>
    internal static class EventSink
    {
        private static readonly object Sync = new object();
        private static TextWriter _out = TextWriter.Null;
        private static DailyTextLog _activityLog;
        private static DailyTextLog _receivedLog;
        private static int _logWriteFailed;

        public static void Init()
        {
            var writer = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false));
            writer.AutoFlush = true;
            writer.NewLine = "\n";
            _out = writer;
        }

        public static void OpenDailyLogs(string directory)
        {
            _activityLog = new DailyTextLog(directory, "log_", null);
            _receivedLog = new DailyTextLog(directory, "diterima_",
                "# waktu | dari | status | nama asli | nama baru | code | bytes | keterangan");
        }

        public static void CloseDailyLogs()
        {
            if (_activityLog != null)
            {
                _activityLog.Close();
            }
            if (_receivedLog != null)
            {
                _receivedLog.Close();
            }
        }

        public static void Log(string level, string message)
        {
            Emit("log", "level", level, "message", message);
            WriteActivity(DateTime.Now, level, message);
        }

        /// <summary>A received file: event for the GUI + one line in the daily txt files.</summary>
        public static void FileEvent(string status, string source, string client, string original, string name,
            string path, string code, long bytes, string message, string previous)
        {
            Emit("file", "status", status, "source", source, "client", client, "original", original, "name", name,
                "path", path, "code", code, "bytes", bytes, "message", message, "previous", previous);

            DateTime now = DateTime.Now;
            string statusText;
            string level = "info";
            string summary;
            switch (status)
            {
                case "saved":
                    statusText = "Disimpan";
                    summary = "Disimpan: " + original + "  ->  " + name;
                    break;
                case "duplicate":
                    statusText = "Duplikat";
                    level = "warn";
                    summary = "Duplikat code " + code + ": " + original + (path != null ? " (disimpan ke _duplikat)" : " (dibuang)");
                    break;
                case "unmatched":
                    statusText = "Tidak sesuai";
                    level = "warn";
                    summary = "Format nama tidak sesuai: " + original +
                              (path != null ? " (disimpan ke _tidak_sesuai)" : " (foto tidak disimpan, dicatat di _log)");
                    break;
                default:
                    statusText = "Gagal";
                    level = "error";
                    summary = "Gagal: " + original + " - " + message;
                    break;
            }

            WriteSafe(_receivedLog, now, Stamp(now) + " | " + Dash(client) + " | " + statusText + " | " + Dash(original) + " | " +
                Dash(name) + " | " + Dash(code) + " | " + bytes.ToString(CultureInfo.InvariantCulture) + " | " +
                (message ?? string.Empty));
            WriteActivity(now, level, summary);
        }

        private static void WriteActivity(DateTime time, string level, string message)
        {
            WriteSafe(_activityLog, time, Stamp(time) + " [" + (level ?? "info").ToUpperInvariant() + "] " + message);
        }

        private static void WriteSafe(DailyTextLog log, DateTime time, string line)
        {
            if (log == null)
            {
                return;
            }
            try
            {
                log.Write(time, line);
            }
            catch (Exception ex)
            {
                // Report once, and only to the GUI (writing it to the file would fail again).
                if (System.Threading.Interlocked.Exchange(ref _logWriteFailed, 1) == 0)
                {
                    Emit("log", "level", "error", "message", "Log txt tidak bisa ditulis: " + ex.Message);
                }
            }
        }

        private static string Stamp(DateTime time)
        {
            return time.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture);
        }

        private static string Dash(string value)
        {
            return string.IsNullOrEmpty(value) ? "-" : value;
        }

        /// <summary>Emit an event: Emit("file", "key1", value1, "key2", value2, ...).</summary>
        public static void Emit(string type, params object[] pairs)
        {
            var sb = new StringBuilder(256);
            sb.Append("{\"type\":");
            AppendString(sb, type);
            sb.Append(",\"time\":");
            AppendString(sb, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
            for (int i = 0; i + 1 < pairs.Length; i += 2)
            {
                sb.Append(',');
                AppendString(sb, Convert.ToString(pairs[i], CultureInfo.InvariantCulture));
                sb.Append(':');
                AppendValue(sb, pairs[i + 1]);
            }
            sb.Append('}');

            lock (Sync)
            {
                try
                {
                    _out.WriteLine(sb.ToString());
                }
                catch (IOException)
                {
                    // GUI closed the pipe; nothing left to report to.
                }
                catch (ObjectDisposedException)
                {
                }
            }
        }

        private static void AppendValue(StringBuilder sb, object value)
        {
            if (value == null)
            {
                sb.Append("null");
            }
            else if (value is bool)
            {
                sb.Append((bool)value ? "true" : "false");
            }
            else if (value is int || value is long || value is short || value is byte)
            {
                sb.Append(Convert.ToString(value, CultureInfo.InvariantCulture));
            }
            else if (value is double || value is float)
            {
                sb.Append(Convert.ToDouble(value).ToString("R", CultureInfo.InvariantCulture));
            }
            else
            {
                AppendString(sb, value.ToString());
            }
        }

        private static void AppendString(StringBuilder sb, string s)
        {
            sb.Append('"');
            if (s != null)
            {
                foreach (char c in s)
                {
                    switch (c)
                    {
                        case '"': sb.Append("\\\""); break;
                        case '\\': sb.Append("\\\\"); break;
                        case '\n': sb.Append("\\n"); break;
                        case '\r': sb.Append("\\r"); break;
                        case '\t': sb.Append("\\t"); break;
                        default:
                            if (c < 0x20 || c > 0x7E)
                            {
                                sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                            }
                            else
                            {
                                sb.Append(c);
                            }
                            break;
                    }
                }
            }
            sb.Append('"');
        }
    }
}
