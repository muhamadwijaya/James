using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace FtpBackend
{
    internal sealed class FtpReply
    {
        public FtpReply(int code, string text)
        {
            Code = code;
            Text = text;
        }

        public int Code { get; private set; }
        public string Text { get; private set; }

        public override string ToString()
        {
            return Text;
        }
    }

    internal sealed class FtpException : Exception
    {
        public FtpException(string command, FtpReply reply)
            : base((command == null ? string.Empty : command + ": ") + reply.Text.Replace('\n', ' '))
        {
            Reply = reply;
        }

        public FtpReply Reply { get; private set; }

        public bool IsLoginFailure
        {
            get { return Reply.Code == 530; }
        }
    }

    internal sealed class RemoteEntry
    {
        public string Directory;
        public string Name;
        public bool IsDirectory;
        public long Size;

        public string FullPath
        {
            get { return FtpClient.Combine(Directory, Name); }
        }
    }

    /// <summary>Minimal passive-mode FTP client: login, list, download, delete.</summary>
    internal sealed class FtpClient : IDisposable
    {
        private static readonly Encoding Utf8 = new UTF8Encoding(false);

        // -rw-r--r--   1 owner group     12345 Oct 13 03:02 3975 264 812_2026_10_10_00_08_46.jpg
        private static readonly Regex UnixLine = new Regex(
            @"^(?<type>[\-dlbcps])[rwxsStT\-]{9}\S*\s+\d+\s+(?:\S+\s+){1,2}(?<size>\d+)\s+[A-Za-z]{3}\s+\d{1,2}\s+(?:\d{1,2}:\d{2}|\d{4})\s(?<name>.+)$",
            RegexOptions.CultureInvariant);

        // 10-13-26  03:02AM               12345 3975 264 812_2026_10_10_00_08_46.jpg   (IIS / Windows)
        private static readonly Regex DosLine = new Regex(
            @"^\d{2}-\d{2}-\d{2,4}\s+\d{1,2}:\d{2}\s*(?:[AaPp][Mm])?\s+(?<size><DIR>|\d+)\s+(?<name>.+)$",
            RegexOptions.CultureInvariant);

        private static readonly Regex PasvReply = new Regex(@"(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)", RegexOptions.CultureInvariant);
        private static readonly Regex EpsvReply = new Regex(@"\(([^\d\s])\1\1(\d+)\1\)", RegexOptions.CultureInvariant);

        private readonly string _host;
        private readonly int _port;
        private readonly int _timeoutSeconds;
        private TcpClient _control;
        private StreamReader _reader;
        private StreamWriter _writer;
        private IPAddress _serverAddress;
        private string _cwd;
        private bool _useEpsv;
        private bool _disposed;

        public FtpClient(string host, int port, int timeoutSeconds)
        {
            _host = host;
            _port = port;
            _timeoutSeconds = timeoutSeconds;
        }

        public bool SupportsMlsd { get; private set; }

        public bool IsConnected
        {
            get { return !_disposed && _control != null && _control.Connected; }
        }

        public async Task ConnectAsync(string user, string password)
        {
            _control = new TcpClient();
            _control.NoDelay = true;
            Task connect = _control.ConnectAsync(_host, _port);
            if (!await AsyncUtil.WithTimeout(connect, _timeoutSeconds))
            {
                Dispose();
                throw new TimeoutException("Server " + _host + ":" + _port + " tidak merespons");
            }
            await connect;

            var remote = (IPEndPoint)_control.Client.RemoteEndPoint;
            _serverAddress = remote.Address.IsIPv4MappedToIPv6 ? remote.Address.MapToIPv4() : remote.Address;
            _useEpsv = _serverAddress.AddressFamily != AddressFamily.InterNetwork;

            NetworkStream stream = _control.GetStream();
            _reader = new StreamReader(stream, Utf8, false, 4096);
            _writer = new StreamWriter(stream, Utf8, 4096);
            _writer.NewLine = "\r\n";
            _writer.AutoFlush = true;

            FtpReply reply = await ReadReplyAsync();
            if (reply.Code != 220)
            {
                throw new FtpException("CONNECT", reply);
            }

            reply = await CommandAsync("USER " + user);
            if (reply.Code == 331)
            {
                reply = await CommandAsync("PASS " + password);
            }
            if (reply.Code != 230 && reply.Code != 202)
            {
                throw new FtpException("LOGIN", reply);
            }

            reply = await CommandAsync("FEAT");
            if (reply.Code == 211)
            {
                string features = reply.Text.ToUpperInvariant();
                SupportsMlsd = features.Contains("MLST") || features.Contains("MLSD");
                if (features.Contains("UTF8"))
                {
                    await CommandAsync("OPTS UTF8 ON");
                }
            }

            reply = await CommandAsync("TYPE I");
            if (reply.Code != 200)
            {
                throw new FtpException("TYPE I", reply);
            }
        }

        public async Task<List<RemoteEntry>> ListAsync(string directory)
        {
            await ChangeDirectoryAsync(directory);
            byte[] raw = null;
            FtpReply reply = null;
            if (SupportsMlsd)
            {
                reply = await TryReceiveAsync("MLSD");
                if (reply == null)
                {
                    raw = _lastData;
                }
                else if (reply.Code == 500 || reply.Code == 502)
                {
                    SupportsMlsd = false;
                }
                else
                {
                    throw new FtpException("MLSD " + directory, reply);
                }
            }
            if (raw == null)
            {
                reply = await TryReceiveAsync("LIST");
                if (reply != null)
                {
                    // Some servers answer an empty folder with 450/550.
                    if (reply.Code == 450 || reply.Code == 550)
                    {
                        return new List<RemoteEntry>();
                    }
                    throw new FtpException("LIST " + directory, reply);
                }
                raw = _lastData;
            }

            var entries = new List<RemoteEntry>();
            string text = Utf8.GetString(raw);
            foreach (string rawLine in text.Split('\n'))
            {
                string line = rawLine.TrimEnd('\r');
                RemoteEntry entry = SupportsMlsd ? ParseMlsd(line) : ParseList(line);
                if (entry != null && entry.Name != "." && entry.Name != "..")
                {
                    entry.Directory = directory;
                    entries.Add(entry);
                }
            }
            return entries;
        }

        public async Task<long> DownloadAsync(string directory, string name, Stream destination, TransferReporter progress)
        {
            await ChangeDirectoryAsync(directory);
            TcpClient data = await OpenDataAsync();
            try
            {
                FtpReply reply = await CommandAsync("RETR " + name);
                if (reply.Code != 150 && reply.Code != 125)
                {
                    throw new FtpException("RETR " + name, reply);
                }
                long bytes;
                using (NetworkStream stream = data.GetStream())
                {
                    bytes = await AsyncUtil.CopyAsync(stream, destination, _timeoutSeconds, progress);
                }
                data.Close();
                reply = await ReadReplyAsync();
                if (reply.Code != 226 && reply.Code != 250)
                {
                    throw new FtpException("RETR " + name, reply);
                }
                return bytes;
            }
            finally
            {
                data.Close();
            }
        }

        public async Task DeleteAsync(string directory, string name)
        {
            await ChangeDirectoryAsync(directory);
            FtpReply reply = await CommandAsync("DELE " + name);
            if (reply.Code != 250 && reply.Code != 200)
            {
                throw new FtpException("DELE " + name, reply);
            }
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }
            _disposed = true;
            try
            {
                if (_control != null && _control.Connected && _writer != null)
                {
                    _writer.WriteLine("QUIT");
                }
            }
            catch (Exception)
            {
            }
            try
            {
                if (_control != null)
                {
                    _control.Close();
                }
            }
            catch (Exception)
            {
            }
        }

        public static string Combine(string directory, string name)
        {
            return (directory ?? "/").TrimEnd('/') + "/" + name;
        }

        private byte[] _lastData;

        /// <summary>Runs a data command; returns null on success (data in _lastData) or the error reply.</summary>
        private async Task<FtpReply> TryReceiveAsync(string command)
        {
            _lastData = null;
            TcpClient data = await OpenDataAsync();
            try
            {
                FtpReply reply = await CommandAsync(command);
                if (reply.Code != 150 && reply.Code != 125)
                {
                    return reply;
                }
                using (var buffer = new MemoryStream())
                {
                    using (NetworkStream stream = data.GetStream())
                    {
                        await AsyncUtil.CopyAsync(stream, buffer, _timeoutSeconds);
                    }
                    data.Close();
                    reply = await ReadReplyAsync();
                    if (reply.Code != 226 && reply.Code != 250)
                    {
                        return reply;
                    }
                    _lastData = buffer.ToArray();
                    return null;
                }
            }
            finally
            {
                data.Close();
            }
        }

        private async Task ChangeDirectoryAsync(string directory)
        {
            if (string.Equals(_cwd, directory, StringComparison.Ordinal))
            {
                return;
            }
            FtpReply reply = await CommandAsync("CWD " + directory);
            if (reply.Code != 250 && reply.Code != 200)
            {
                _cwd = null;
                throw new FtpException("CWD " + directory, reply);
            }
            _cwd = directory;
        }

        private async Task<TcpClient> OpenDataAsync()
        {
            int port = -1;
            if (!_useEpsv)
            {
                FtpReply pasv = await CommandAsync("PASV");
                Match m = PasvReply.Match(pasv.Text);
                if (pasv.Code == 227 && m.Success)
                {
                    port = int.Parse(m.Groups[5].Value, CultureInfo.InvariantCulture) * 256 +
                           int.Parse(m.Groups[6].Value, CultureInfo.InvariantCulture);
                }
                else
                {
                    _useEpsv = true;
                }
            }
            if (port < 0)
            {
                FtpReply epsv = await CommandAsync("EPSV");
                Match m = EpsvReply.Match(epsv.Text);
                if (epsv.Code != 229 || !m.Success)
                {
                    throw new FtpException("PASV/EPSV", epsv);
                }
                port = int.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture);
            }

            // Always connect to the address of the control connection: the address in the
            // PASV reply is often a private/NAT address that is not reachable from here.
            var data = new TcpClient(_serverAddress.AddressFamily);
            try
            {
                Task connect = data.ConnectAsync(_serverAddress, port);
                if (!await AsyncUtil.WithTimeout(connect, _timeoutSeconds))
                {
                    throw new TimeoutException("Koneksi data ke port " + port + " timeout");
                }
                await connect;
                return data;
            }
            catch
            {
                data.Close();
                throw;
            }
        }

        private async Task<FtpReply> CommandAsync(string command)
        {
            await _writer.WriteLineAsync(command);
            return await ReadReplyAsync();
        }

        private async Task<FtpReply> ReadReplyAsync()
        {
            string first = await ReadLineAsync();
            int code;
            if (first.Length < 3 || !int.TryParse(first.Substring(0, 3), NumberStyles.None, CultureInfo.InvariantCulture, out code))
            {
                throw new IOException("Balasan FTP tidak valid: " + first);
            }

            var text = new StringBuilder(first);
            if (first.Length > 3 && first[3] == '-')
            {
                string end = first.Substring(0, 3);
                while (true)
                {
                    string line = await ReadLineAsync();
                    text.Append('\n').Append(line);
                    if (line.StartsWith(end + " ", StringComparison.Ordinal) || line == end)
                    {
                        break;
                    }
                }
            }
            return new FtpReply(code, text.ToString());
        }

        private async Task<string> ReadLineAsync()
        {
            Task<string> read = _reader.ReadLineAsync();
            if (!await AsyncUtil.WithTimeout(read, _timeoutSeconds))
            {
                throw new TimeoutException("Server tidak membalas dalam " + _timeoutSeconds + " detik");
            }
            string line = await read;
            if (line == null)
            {
                throw new IOException("Koneksi ditutup oleh server");
            }
            return line;
        }

        private static RemoteEntry ParseMlsd(string line)
        {
            // type=file;size=12345;modify=20261013030201; name with spaces.jpg
            int space = line.IndexOf(' ');
            if (space <= 0)
            {
                return null;
            }
            var entry = new RemoteEntry();
            entry.Name = line.Substring(space + 1);
            string type = null;
            foreach (string fact in line.Substring(0, space).Split(';'))
            {
                int eq = fact.IndexOf('=');
                if (eq <= 0)
                {
                    continue;
                }
                string key = fact.Substring(0, eq).Trim().ToLowerInvariant();
                string value = fact.Substring(eq + 1).Trim();
                if (key == "type")
                {
                    type = value.ToLowerInvariant();
                }
                else if (key == "size")
                {
                    long size;
                    if (long.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out size))
                    {
                        entry.Size = size;
                    }
                }
            }
            if (type == "cdir" || type == "pdir")
            {
                return null;
            }
            entry.IsDirectory = type == "dir";
            return entry;
        }

        private static RemoteEntry ParseList(string line)
        {
            Match m = UnixLine.Match(line);
            if (m.Success)
            {
                string type = m.Groups["type"].Value;
                if (type != "-" && type != "d" && type != "l")
                {
                    return null;
                }
                var entry = new RemoteEntry();
                entry.Name = m.Groups["name"].Value.TrimStart(' ');
                if (type == "l")
                {
                    int arrow = entry.Name.IndexOf(" -> ", StringComparison.Ordinal);
                    if (arrow > 0)
                    {
                        entry.Name = entry.Name.Substring(0, arrow);
                    }
                }
                entry.IsDirectory = type == "d";
                entry.Size = long.Parse(m.Groups["size"].Value, CultureInfo.InvariantCulture);
                return entry;
            }

            m = DosLine.Match(line);
            if (m.Success)
            {
                var entry = new RemoteEntry();
                entry.Name = m.Groups["name"].Value;
                string size = m.Groups["size"].Value;
                entry.IsDirectory = size.Equals("<DIR>", StringComparison.OrdinalIgnoreCase);
                entry.Size = entry.IsDirectory ? 0 : long.Parse(size, CultureInfo.InvariantCulture);
                return entry;
            }
            return null;
        }
    }
}
