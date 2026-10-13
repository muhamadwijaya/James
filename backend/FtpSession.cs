using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace FtpBackend
{
    internal sealed class UploadRecord
    {
        public long Size;
        public DateTime Time;
        public PhotoResult Result;
    }

    internal sealed class DataConnection : IDisposable
    {
        private readonly TcpClient _client;

        public DataConnection(TcpClient client)
        {
            _client = client;
            Stream = client.GetStream();
        }

        public NetworkStream Stream { get; private set; }

        /// <summary>Signals end-of-data to the peer after we sent something.</summary>
        public void FinishSending()
        {
            try
            {
                _client.Client.Shutdown(SocketShutdown.Send);
            }
            catch (Exception)
            {
            }
        }

        public void Dispose()
        {
            try
            {
                Stream.Dispose();
            }
            catch (Exception)
            {
            }
            try
            {
                _client.Close();
            }
            catch (Exception)
            {
            }
        }
    }

    /// <summary>
    /// One FTP control connection. The file system is virtual: directories always
    /// "exist", uploads are handed to <see cref="PhotoProcessor"/> and downloads are refused.
    /// </summary>
    internal sealed class FtpSession
    {
        private const int MaxRememberedUploads = 500;
        private static readonly Encoding Utf8 = new UTF8Encoding(false);

        private readonly FtpServer _server;
        private readonly ServerOptions _options;
        private readonly PhotoProcessor _processor;
        private readonly TcpClient _client;
        private readonly IPAddress _remoteIp;
        private readonly Dictionary<string, UploadRecord> _uploads = new Dictionary<string, UploadRecord>(StringComparer.Ordinal);
        private readonly Queue<string> _uploadOrder = new Queue<string>();

        private StreamReader _reader;
        private StreamWriter _writer;
        private string _user;
        private bool _loggedIn;
        private int _failedLogins;
        private string _cwd = "/";
        private TcpListener _passive;
        private IPEndPoint _active;
        private string _renameFrom;
        private volatile bool _busy;
        private volatile bool _stopRequested;
        private volatile bool _closed;

        public FtpSession(int id, TcpClient client, FtpServer server)
        {
            Id = id;
            _client = client;
            _server = server;
            _options = server.Options;
            _processor = server.Processor;
            var remote = (IPEndPoint)client.Client.RemoteEndPoint;
            _remoteIp = Normalize(remote.Address);
            Remote = _remoteIp + ":" + remote.Port.ToString(CultureInfo.InvariantCulture);
        }

        public int Id { get; private set; }
        public string Remote { get; private set; }

        public void RequestStop()
        {
            _stopRequested = true;
            if (!_busy)
            {
                Abort();
            }
        }

        public void Abort()
        {
            _closed = true;
            ClosePassive();
            try
            {
                _client.Close();
            }
            catch (Exception)
            {
            }
        }

        public async Task RunAsync()
        {
            try
            {
                NetworkStream stream = _client.GetStream();
                _reader = new StreamReader(stream, Utf8, false, 4096);
                _writer = new StreamWriter(stream, Utf8, 4096);
                _writer.NewLine = "\r\n";
                _writer.AutoFlush = true;

                await ReplyAsync(220, "FTP Photo Renamer ready.");
                while (!_closed)
                {
                    Task<string> read = _reader.ReadLineAsync();
                    if (!await AsyncUtil.WithTimeout(read, _options.IdleTimeoutSeconds))
                    {
                        await ReplyAsync(421, "Idle timeout, closing connection.");
                        break;
                    }

                    string line = await read;
                    if (line == null)
                    {
                        break;
                    }

                    line = line.TrimStart();
                    if (line.Length == 0)
                    {
                        continue;
                    }

                    int space = line.IndexOf(' ');
                    string cmd = (space < 0 ? line : line.Substring(0, space)).ToUpperInvariant();
                    string arg = space < 0 ? string.Empty : line.Substring(space + 1);
                    if (cmd != "PASS")
                    {
                        arg = arg.Trim();
                    }

                    _busy = true;
                    bool keepOpen;
                    try
                    {
                        keepOpen = await HandleAsync(cmd, arg);
                    }
                    finally
                    {
                        _busy = false;
                    }

                    if (!keepOpen)
                    {
                        break;
                    }
                    if (_stopRequested)
                    {
                        await ReplyAsync(421, "Server is shutting down.");
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                if (!_closed && !(ex is IOException) && !(ex is ObjectDisposedException))
                {
                    EventSink.Log("warn", "Sesi " + Remote + " error: " + ex.Message);
                }
            }
            finally
            {
                Abort();
            }
        }

        private static bool AllowedBeforeLogin(string cmd)
        {
            switch (cmd)
            {
                case "USER":
                case "PASS":
                case "QUIT":
                case "NOOP":
                case "SYST":
                case "FEAT":
                case "OPTS":
                case "HELP":
                case "AUTH":
                case "PBSZ":
                case "PROT":
                case "CLNT":
                case "HOST":
                    return true;
                default:
                    return false;
            }
        }

        private async Task<bool> HandleAsync(string cmd, string arg)
        {
            if (!_loggedIn && !AllowedBeforeLogin(cmd))
            {
                await ReplyAsync(530, "Please login with USER and PASS.");
                return true;
            }

            switch (cmd)
            {
                case "USER":
                    _user = arg;
                    _loggedIn = false;
                    await ReplyAsync(331, "Password required for " + arg + ".");
                    return true;

                case "PASS":
                    return await CmdPassAsync(arg);

                case "QUIT":
                    await ReplyAsync(221, "Goodbye.");
                    return false;

                case "NOOP":
                case "CLNT":
                case "MODE":
                case "STRU":
                case "SITE":
                    await ReplyAsync(200, "OK.");
                    return true;

                case "HOST":
                    await ReplyAsync(220, "Host accepted.");
                    return true;

                case "SYST":
                    await ReplyAsync(215, "UNIX Type: L8");
                    return true;

                case "FEAT":
                    await _writer.WriteLineAsync("211-Features:\r\n UTF8\r\n PASV\r\n EPSV\r\n EPRT\r\n SIZE\r\n MLSD\r\n211 End");
                    return true;

                case "OPTS":
                    if (arg.StartsWith("UTF8", StringComparison.OrdinalIgnoreCase))
                    {
                        await ReplyAsync(200, "UTF8 mode enabled.");
                    }
                    else
                    {
                        await ReplyAsync(501, "Option not supported.");
                    }
                    return true;

                case "HELP":
                    await ReplyAsync(214, "Upload only FTP server.");
                    return true;

                case "STAT":
                    await ReplyAsync(211, "FTP Photo Renamer, logged in as " + _user + ".");
                    return true;

                case "AUTH":
                case "PBSZ":
                case "PROT":
                    await ReplyAsync(502, "TLS is not supported.");
                    return true;

                case "ACCT":
                    await ReplyAsync(202, "Account not needed.");
                    return true;

                case "TYPE":
                    await ReplyAsync(200, "Type set to " + arg + ".");
                    return true;

                case "ALLO":
                    await ReplyAsync(202, "No storage allocation necessary.");
                    return true;

                case "REST":
                    if (arg == "0")
                    {
                        await ReplyAsync(350, "Restarting at 0.");
                    }
                    else
                    {
                        await ReplyAsync(504, "Resume is not supported.");
                    }
                    return true;

                case "ABOR":
                    await ReplyAsync(226, "No transfer to abort.");
                    return true;

                case "PWD":
                case "XPWD":
                    await ReplyAsync(257, "\"" + _cwd.Replace("\"", "\"\"") + "\" is the current directory.");
                    return true;

                case "CWD":
                case "XCWD":
                    _cwd = ResolvePath(arg);
                    await ReplyAsync(250, "Directory changed to " + _cwd + ".");
                    return true;

                case "CDUP":
                case "XCUP":
                    _cwd = ResolvePath("..");
                    await ReplyAsync(250, "Directory changed to " + _cwd + ".");
                    return true;

                case "MKD":
                case "XMKD":
                    await ReplyAsync(257, "\"" + ResolvePath(arg).Replace("\"", "\"\"") + "\" created.");
                    return true;

                case "RMD":
                case "XRMD":
                    await ReplyAsync(250, "Directory removed.");
                    return true;

                case "PASV":
                    return await CmdPassiveAsync(false, arg);

                case "EPSV":
                    return await CmdPassiveAsync(true, arg);

                case "PORT":
                    return await CmdPortAsync(arg);

                case "EPRT":
                    return await CmdExtendedPortAsync(arg);

                case "STOR":
                case "STOU":
                case "APPE":
                    return await CmdStoreAsync(cmd, arg);

                case "LIST":
                case "NLST":
                case "MLSD":
                    return await CmdListAsync(cmd, arg);

                case "SIZE":
                    {
                        UploadRecord record;
                        if (_uploads.TryGetValue(ResolvePath(arg), out record))
                        {
                            await ReplyAsync(213, record.Size.ToString(CultureInfo.InvariantCulture));
                        }
                        else
                        {
                            await ReplyAsync(550, "File not found.");
                        }
                        return true;
                    }

                case "MDTM":
                case "RETR":
                    await ReplyAsync(550, "Download is not supported.");
                    return true;

                case "DELE":
                    CmdDelete(arg);
                    await ReplyAsync(250, "File deleted.");
                    return true;

                case "RNFR":
                    _renameFrom = ResolvePath(arg);
                    await ReplyAsync(350, "Ready for RNTO.");
                    return true;

                case "RNTO":
                    return await CmdRenameToAsync(arg);

                default:
                    await ReplyAsync(502, "Command not implemented.");
                    return true;
            }
        }

        private async Task<bool> CmdPassAsync(string password)
        {
            if (_user == null)
            {
                await ReplyAsync(503, "Login with USER first.");
                return true;
            }

            bool ok = _options.AllowAnyLogin ||
                      (string.Equals(_user, _options.User, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(password, _options.Password, StringComparison.Ordinal));
            if (ok)
            {
                _loggedIn = true;
                _failedLogins = 0;
                EventSink.Log("info", "Login berhasil: " + _user + " dari " + Remote);
                await ReplyAsync(230, "Login successful.");
                return true;
            }

            _failedLogins++;
            EventSink.Log("warn", "Login gagal: user '" + _user + "' dari " + Remote);
            await Task.Delay(1000);
            await ReplyAsync(530, "Login incorrect.");
            if (_failedLogins >= 5)
            {
                await ReplyAsync(421, "Too many failed logins.");
                return false;
            }
            return true;
        }

        private async Task<bool> CmdPassiveAsync(bool extended, string arg)
        {
            if (extended && arg.Equals("ALL", StringComparison.OrdinalIgnoreCase))
            {
                await ReplyAsync(200, "EPSV ALL accepted.");
                return true;
            }

            ClosePassive();
            _active = null;

            IPAddress local = Normalize(((IPEndPoint)_client.Client.LocalEndPoint).Address);
            if (!extended && local.AddressFamily != AddressFamily.InterNetwork)
            {
                await ReplyAsync(425, "PASV needs IPv4, use EPSV.");
                return true;
            }

            TcpListener listener = null;
            try
            {
                listener = _server.OpenPassiveListener(local);
            }
            catch (Exception)
            {
                listener = null;
            }
            if (listener == null)
            {
                EventSink.Log("warn", "Tidak ada port pasif yang bebas untuk " + Remote);
                await ReplyAsync(425, "No free passive port.");
                return true;
            }

            _passive = listener;
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            if (extended)
            {
                await ReplyAsync(229, "Entering Extended Passive Mode (|||" + port.ToString(CultureInfo.InvariantCulture) + "|).");
            }
            else
            {
                byte[] ip = local.GetAddressBytes();
                string text = string.Format(CultureInfo.InvariantCulture, "Entering Passive Mode ({0},{1},{2},{3},{4},{5}).",
                    ip[0], ip[1], ip[2], ip[3], port >> 8, port & 0xFF);
                await ReplyAsync(227, text);
            }
            return true;
        }

        private async Task<bool> CmdPortAsync(string arg)
        {
            string[] parts = arg.Split(',');
            byte[] ip = new byte[4];
            int p1 = 0, p2 = 0;
            bool valid = parts.Length == 6 &&
                         byte.TryParse(parts[0].Trim(), out ip[0]) && byte.TryParse(parts[1].Trim(), out ip[1]) &&
                         byte.TryParse(parts[2].Trim(), out ip[2]) && byte.TryParse(parts[3].Trim(), out ip[3]) &&
                         int.TryParse(parts[4].Trim(), out p1) && int.TryParse(parts[5].Trim(), out p2) &&
                         p1 >= 0 && p1 <= 255 && p2 >= 0 && p2 <= 255;
            if (!valid)
            {
                await ReplyAsync(501, "Syntax error in PORT.");
                return true;
            }
            return await SetActiveAsync(new IPAddress(ip), p1 * 256 + p2);
        }

        private async Task<bool> CmdExtendedPortAsync(string arg)
        {
            // EPRT |1|192.168.1.10|6275|
            IPAddress address = null;
            int port = 0;
            bool valid = false;
            if (arg.Length > 1)
            {
                string[] parts = arg.Split(arg[0]);
                valid = parts.Length >= 4 && IPAddress.TryParse(parts[2], out address) &&
                        int.TryParse(parts[3], NumberStyles.Integer, CultureInfo.InvariantCulture, out port);
            }
            if (!valid)
            {
                await ReplyAsync(501, "Syntax error in EPRT.");
                return true;
            }
            return await SetActiveAsync(address, port);
        }

        private async Task<bool> SetActiveAsync(IPAddress address, int port)
        {
            // Only allow data connections back to the client itself (no FTP bounce).
            if (!Normalize(address).Equals(_remoteIp) || port < 1 || port > 65535)
            {
                await ReplyAsync(504, "Data address must match the client address.");
                return true;
            }
            ClosePassive();
            _active = new IPEndPoint(address, port);
            await ReplyAsync(200, "PORT command successful.");
            return true;
        }

        private async Task<bool> CmdStoreAsync(string cmd, string arg)
        {
            if (arg.Length == 0 && cmd != "STOU")
            {
                await ReplyAsync(501, "File name required.");
                return true;
            }
            if (arg.Length == 0)
            {
                arg = "upload_" + DateTime.Now.ToString("yyyyMMdd_HHmmss_fff", CultureInfo.InvariantCulture) + ".jpg";
            }

            string virtualPath = ResolvePath(arg);
            string fileName = FileNameOf(virtualPath);
            if (fileName.Length == 0)
            {
                await ReplyAsync(553, "File name not allowed.");
                return true;
            }

            string tempPath = null;
            string prepareError = null;
            try
            {
                tempPath = _processor.CreateTempPath();
            }
            catch (Exception ex)
            {
                prepareError = ex.Message;
            }
            if (prepareError != null)
            {
                EventSink.Log("error", "Folder tujuan tidak bisa dipakai: " + prepareError);
                await ReplyAsync(451, "Local error: " + prepareError);
                return true;
            }

            await ReplyAsync(150, "Opening data connection for " + fileName + ".");
            DataConnection data = await OpenDataAsync();
            if (data == null)
            {
                await ReplyAsync(425, "Can't open data connection.");
                return true;
            }

            long bytes = 0;
            string transferError = null;
            try
            {
                using (data)
                using (var file = new FileStream(tempPath, FileMode.CreateNew, FileAccess.Write, FileShare.None, AsyncUtil.BufferSize, true))
                {
                    bytes = await AsyncUtil.CopyAsync(data.Stream, file, _options.DataTimeoutSeconds);
                }
            }
            catch (Exception ex)
            {
                transferError = ex.Message;
            }

            if (transferError != null)
            {
                PhotoProcessor.TryDelete(tempPath);
                EventSink.Emit("file", "status", "error", "source", "upload", "client", _remoteIp.ToString(),
                    "original", fileName, "name", null, "path", null, "code", null, "bytes", bytes,
                    "message", "Transfer gagal: " + transferError);
                await ReplyAsync(426, "Transfer aborted.");
                return true;
            }

            PhotoResult result = _processor.Complete(tempPath, fileName);
            if (result.Status == PhotoStatus.Error)
            {
                PhotoProcessor.TryDelete(tempPath);
            }

            var record = new UploadRecord();
            record.Size = bytes;
            record.Time = DateTime.Now;
            record.Result = result;
            RememberUpload(virtualPath, record);

            EmitFileEvent(result, "upload", bytes, null);
            if (result.Status == PhotoStatus.Error)
            {
                await ReplyAsync(451, "Local error: " + result.Message);
            }
            else
            {
                await ReplyAsync(226, "Transfer complete.");
            }
            return true;
        }

        private async Task<bool> CmdListAsync(string cmd, string arg)
        {
            // Ignore ls-style options such as "-la".
            string target = arg;
            while (target.StartsWith("-", StringComparison.Ordinal))
            {
                int space = target.IndexOf(' ');
                target = space < 0 ? string.Empty : target.Substring(space + 1).TrimStart();
            }
            string dir = target.Length == 0 ? _cwd : ResolvePath(target);

            var sb = new StringBuilder();
            foreach (KeyValuePair<string, UploadRecord> entry in _uploads)
            {
                if (!string.Equals(ParentOf(entry.Key), dir, StringComparison.Ordinal))
                {
                    continue;
                }
                string name = FileNameOf(entry.Key);
                if (cmd == "NLST")
                {
                    sb.Append(name).Append("\r\n");
                }
                else if (cmd == "MLSD")
                {
                    sb.Append("type=file;size=").Append(entry.Value.Size).Append("; ").Append(name).Append("\r\n");
                }
                else
                {
                    sb.AppendFormat(CultureInfo.InvariantCulture, "-rw-r--r-- 1 ftp ftp {0,12} {1:MMM dd HH:mm} {2}\r\n",
                        entry.Value.Size, entry.Value.Time, name);
                }
            }

            await ReplyAsync(150, "Here comes the directory listing.");
            DataConnection data = await OpenDataAsync();
            if (data == null)
            {
                await ReplyAsync(425, "Can't open data connection.");
                return true;
            }

            bool sent = false;
            try
            {
                using (data)
                {
                    byte[] payload = Utf8.GetBytes(sb.ToString());
                    await data.Stream.WriteAsync(payload, 0, payload.Length);
                    data.FinishSending();
                }
                sent = true;
            }
            catch (Exception)
            {
                sent = false;
            }
            await ReplyAsync(sent ? 226 : 426, sent ? "Directory send OK." : "Transfer aborted.");
            return true;
        }

        private void CmdDelete(string arg)
        {
            // Cameras sometimes upload a test file and delete it. Only files that were
            // not accepted as photos are really deleted; saved photos are kept.
            string path = ResolvePath(arg);
            UploadRecord record;
            if (_uploads.TryGetValue(path, out record))
            {
                if (record.Result.Status == PhotoStatus.Unmatched)
                {
                    PhotoProcessor.TryDelete(record.Result.FinalPath);
                    EventSink.Log("info", "File uji dihapus atas permintaan klien: " + record.Result.OriginalName);
                }
                _uploads.Remove(path);
            }
        }

        private async Task<bool> CmdRenameToAsync(string arg)
        {
            string from = _renameFrom;
            _renameFrom = null;
            if (from == null)
            {
                await ReplyAsync(503, "RNFR required first.");
                return true;
            }

            UploadRecord record;
            if (!_uploads.TryGetValue(from, out record))
            {
                await ReplyAsync(550, "File not found.");
                return true;
            }

            string to = ResolvePath(arg);
            // Some devices upload under a temporary name and rename afterwards.
            if (record.Result.Status == PhotoStatus.Unmatched && File.Exists(record.Result.FinalPath))
            {
                PhotoResult result = _processor.Complete(record.Result.FinalPath, FileNameOf(to));
                if (result.Status != PhotoStatus.Error)
                {
                    record.Result = result;
                    EmitFileEvent(result, "rename", record.Size, "unmatched");
                }
                else
                {
                    EventSink.Log("error", "Gagal memproses rename " + FileNameOf(from) + ": " + result.Message);
                }
            }

            _uploads.Remove(from);
            RememberUpload(to, record);
            await ReplyAsync(250, "Rename successful.");
            return true;
        }

        private void EmitFileEvent(PhotoResult result, string source, long bytes, string previous)
        {
            string status;
            switch (result.Status)
            {
                case PhotoStatus.Saved: status = "saved"; break;
                case PhotoStatus.Duplicate: status = "duplicate"; break;
                case PhotoStatus.Unmatched: status = "unmatched"; break;
                default: status = "error"; break;
            }
            EventSink.Emit("file", "status", status, "source", source, "client", _remoteIp.ToString(),
                "original", result.OriginalName, "name", result.NewName, "path", result.FinalPath,
                "code", result.Code, "bytes", bytes, "message", result.Message, "previous", previous);
        }

        private void RememberUpload(string virtualPath, UploadRecord record)
        {
            _uploads[virtualPath] = record;
            _uploadOrder.Enqueue(virtualPath);
            while (_uploadOrder.Count > MaxRememberedUploads)
            {
                string old = _uploadOrder.Dequeue();
                if (!_uploadOrder.Contains(old))
                {
                    _uploads.Remove(old);
                }
            }
        }

        private async Task<DataConnection> OpenDataAsync()
        {
            TcpListener listener = _passive;
            IPEndPoint active = _active;
            _passive = null;
            _active = null;

            if (listener != null)
            {
                try
                {
                    Task<TcpClient> accept = listener.AcceptTcpClientAsync();
                    if (!await AsyncUtil.WithTimeout(accept, _options.DataTimeoutSeconds))
                    {
                        return null;
                    }
                    TcpClient client = await accept;
                    IPAddress peer = Normalize(((IPEndPoint)client.Client.RemoteEndPoint).Address);
                    if (!peer.Equals(_remoteIp))
                    {
                        EventSink.Log("warn", "Koneksi data dari " + peer + " ditolak (bukan " + _remoteIp + ")");
                        client.Close();
                        return null;
                    }
                    return new DataConnection(client);
                }
                catch (Exception)
                {
                    return null;
                }
                finally
                {
                    listener.Stop();
                }
            }

            if (active != null)
            {
                var client = new TcpClient(active.AddressFamily);
                try
                {
                    Task connect = client.ConnectAsync(active.Address, active.Port);
                    if (!await AsyncUtil.WithTimeout(connect, _options.DataTimeoutSeconds))
                    {
                        client.Close();
                        return null;
                    }
                    await connect;
                    return new DataConnection(client);
                }
                catch (Exception)
                {
                    client.Close();
                    return null;
                }
            }

            return null;
        }

        private Task ReplyAsync(int code, string message)
        {
            string clean = (message ?? string.Empty).Replace('\r', ' ').Replace('\n', ' ');
            return _writer.WriteLineAsync(code.ToString(CultureInfo.InvariantCulture) + " " + clean);
        }

        private void ClosePassive()
        {
            TcpListener listener = _passive;
            _passive = null;
            if (listener != null)
            {
                try
                {
                    listener.Stop();
                }
                catch (Exception)
                {
                }
            }
        }

        private string ResolvePath(string arg)
        {
            string path = (arg ?? string.Empty).Replace('\\', '/');
            string combined = path.StartsWith("/", StringComparison.Ordinal) ? path : _cwd.TrimEnd('/') + "/" + path;
            var parts = new List<string>();
            foreach (string segment in combined.Split('/'))
            {
                if (segment.Length == 0 || segment == ".")
                {
                    continue;
                }
                if (segment == "..")
                {
                    if (parts.Count > 0)
                    {
                        parts.RemoveAt(parts.Count - 1);
                    }
                    continue;
                }
                parts.Add(segment);
            }
            return "/" + string.Join("/", parts);
        }

        private static string FileNameOf(string virtualPath)
        {
            int slash = virtualPath.LastIndexOf('/');
            return slash < 0 ? virtualPath : virtualPath.Substring(slash + 1);
        }

        private static string ParentOf(string virtualPath)
        {
            int slash = virtualPath.LastIndexOf('/');
            return slash <= 0 ? "/" : virtualPath.Substring(0, slash);
        }

        private static IPAddress Normalize(IPAddress address)
        {
            return address.IsIPv4MappedToIPv6 ? address.MapToIPv4() : address;
        }
    }
}
