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
    /// </summary>
    internal static class EventSink
    {
        private static readonly object Sync = new object();
        private static TextWriter _out = TextWriter.Null;

        public static void Init()
        {
            var writer = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false));
            writer.AutoFlush = true;
            writer.NewLine = "\n";
            _out = writer;
        }

        public static void Log(string level, string message)
        {
            Emit("log", "level", level, "message", message);
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
