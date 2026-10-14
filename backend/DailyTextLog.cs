using System;
using System.Globalization;
using System.IO;
using System.Text;

namespace FtpBackend
{
    /// <summary>
    /// Append-only text log that starts a new file every day: {prefix}yyyy-MM-dd.txt.
    /// The file stays open between writes (fast) and can be read in Notepad meanwhile.
    /// </summary>
    internal sealed class DailyTextLog
    {
        private readonly object _sync = new object();
        private readonly string _directory;
        private readonly string _prefix;
        private readonly string _header;
        private string _date;
        private StreamWriter _writer;

        public DailyTextLog(string directory, string prefix, string header)
        {
            _directory = directory;
            _prefix = prefix;
            _header = header;
        }

        /// <summary>Writes one line to today's file and returns that file's path.</summary>
        public string Write(DateTime time, string line)
        {
            string date = time.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            lock (_sync)
            {
                try
                {
                    WriteLine(date, line);
                }
                catch (IOException)
                {
                    // e.g. the _log folder was deleted while running: reopen once.
                    CloseWriter();
                    WriteLine(date, line);
                }
                return PathFor(date);
            }
        }

        public void Close()
        {
            lock (_sync)
            {
                CloseWriter();
            }
        }

        private void WriteLine(string date, string line)
        {
            if (_writer == null || date != _date)
            {
                Open(date);
            }
            _writer.WriteLine(line);
        }

        private void Open(string date)
        {
            CloseWriter();
            Directory.CreateDirectory(_directory);
            var stream = new FileStream(PathFor(date), FileMode.Append, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete);
            var writer = new StreamWriter(stream, new UTF8Encoding(false));
            writer.NewLine = "\r\n";
            writer.AutoFlush = true;
            if (stream.Length == 0 && _header != null)
            {
                writer.WriteLine(_header);
            }
            _writer = writer;
            _date = date;
        }

        private void CloseWriter()
        {
            if (_writer != null)
            {
                try
                {
                    _writer.Dispose();
                }
                catch (Exception)
                {
                }
                _writer = null;
            }
        }

        private string PathFor(string date)
        {
            return Path.Combine(_directory, _prefix + date + ".txt");
        }
    }
}
