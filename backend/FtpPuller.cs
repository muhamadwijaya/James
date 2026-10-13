using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace FtpBackend
{
    internal sealed class ClientOptions
    {
        public string Host;
        public int Port;
        public string User;
        public string Password;
        public string RemoteDir;
        public bool Recursive;
        public int MaxDepth;
        public int IntervalSeconds;
        public int Workers;
        public bool DeleteAfterDownload;
        public int TimeoutSeconds;
        public string[] Extensions;
    }

    /// <summary>
    /// Client mode: logs in to an FTP server, scans a folder periodically and downloads
    /// new photos with several parallel connections. Downloaded photos go through the same
    /// <see cref="PhotoProcessor"/> (rename + one file per code) as uploads in server mode.
    /// </summary>
    internal sealed class FtpPuller
    {
        private readonly ClientOptions _options;
        private readonly PhotoProcessor _processor;
        private readonly CancellationTokenSource _cts = new CancellationTokenSource();
        private readonly ConcurrentQueue<RemoteEntry> _queue = new ConcurrentQueue<RemoteEntry>();
        private readonly SemaphoreSlim _queued = new SemaphoreSlim(0);
        // remote path -> code of the photo ("" when the name does not match the format)
        private readonly ConcurrentDictionary<string, string> _inFlight = new ConcurrentDictionary<string, string>(StringComparer.Ordinal);
        private readonly ConcurrentDictionary<FtpClient, byte> _openClients = new ConcurrentDictionary<FtpClient, byte>();
        private readonly object _sync = new object();
        private readonly HashSet<string> _done = new HashSet<string>(StringComparer.Ordinal);
        private readonly Dictionary<string, DateTime> _retryAfter = new Dictionary<string, DateTime>(StringComparer.Ordinal);
        private readonly Dictionary<string, int> _failures = new Dictionary<string, int>(StringComparer.Ordinal);
        private readonly string _stateFile;
        private Dictionary<string, long> _lastSizes = new Dictionary<string, long>(StringComparer.Ordinal);
        private bool _stateDirty;
        private FtpClient _lister;
        private Task _listerTask;
        private Task[] _workerTasks = new Task[0];
        private int _connections;
        private bool _linkUp;

        public FtpPuller(ClientOptions options, PhotoProcessor processor)
        {
            _options = options;
            _processor = processor;
            _stateFile = Path.Combine(processor.IncomingDir, "remote_" +
                PhotoProcessor.SanitizeFileName(options.Host).Replace(' ', '_') + "_" +
                options.Port.ToString(CultureInfo.InvariantCulture) + ".txt");
        }

        /// <summary>
        /// Connects once to validate the settings. Returns an error message when the login
        /// is refused (wrong settings); network problems are retried in the background.
        /// </summary>
        public string Start()
        {
            LoadState();
            try
            {
                _lister = Connect().GetAwaiter().GetResult();
                SetLink(true, null);
            }
            catch (FtpException ex)
            {
                if (ex.IsLoginFailure)
                {
                    return "Login ke server FTP " + Describe() + " ditolak. Periksa username dan password.";
                }
                SetLink(false, ex.Message);
            }
            catch (Exception ex)
            {
                SetLink(false, ex.Message);
            }

            CancellationToken token = _cts.Token;
            _listerTask = Task.Run(() => ListerLoopAsync(token));
            int workers = Math.Max(1, _options.Workers);
            _workerTasks = new Task[workers];
            for (int i = 0; i < workers; i++)
            {
                _workerTasks[i] = Task.Run(() => WorkerLoopAsync(token));
            }
            return null;
        }

        /// <summary>Stops scanning, lets running downloads finish (max ~10 s), then disconnects.</summary>
        public void Stop()
        {
            _cts.Cancel();
            FtpClient lister = _lister;
            if (lister != null)
            {
                lister.Dispose();
            }

            if (!WaitAll(10000))
            {
                foreach (FtpClient client in _openClients.Keys)
                {
                    client.Dispose();
                }
                WaitAll(3000);
            }
            SaveState(true);
        }

        private bool WaitAll(int milliseconds)
        {
            var all = new List<Task>(_workerTasks);
            if (_listerTask != null)
            {
                all.Add(_listerTask);
            }
            try
            {
                return Task.WaitAll(all.ToArray(), milliseconds);
            }
            catch (AggregateException)
            {
                return true;
            }
        }

        private string Describe()
        {
            return _options.Host + ":" + _options.Port.ToString(CultureInfo.InvariantCulture);
        }

        private async Task<FtpClient> Connect()
        {
            var client = new FtpClient(_options.Host, _options.Port, _options.TimeoutSeconds);
            try
            {
                await client.ConnectAsync(_options.User, _options.Password);
            }
            catch
            {
                client.Dispose();
                throw;
            }
            _openClients[client] = 0;
            ChangeConnections(1);
            return client;
        }

        private void Release(ref FtpClient client)
        {
            if (client == null)
            {
                return;
            }
            byte ignored;
            if (_openClients.TryRemove(client, out ignored))
            {
                ChangeConnections(-1);
            }
            client.Dispose();
            client = null;
        }

        private async Task ListerLoopAsync(CancellationToken token)
        {
            int failures = 0;
            while (!token.IsCancellationRequested)
            {
                string error = null;
                try
                {
                    if (_lister == null || !_lister.IsConnected)
                    {
                        Release(ref _lister);
                        _lister = await Connect();
                    }
                    var found = new List<RemoteEntry>();
                    bool complete = await ScanAsync(_lister, NormalizeDir(_options.RemoteDir), 0, found, token);
                    if (token.IsCancellationRequested)
                    {
                        break;
                    }
                    // Names start with code + date, folders are usually dates: oldest photos first.
                    found.Sort((a, b) => string.CompareOrdinal(a.FullPath, b.FullPath));
                    SetLink(true, null);
                    failures = 0;
                    Enqueue(found, complete);
                    SaveState(false);
                }
                catch (Exception ex)
                {
                    error = ex.Message;
                }

                if (error != null)
                {
                    if (token.IsCancellationRequested)
                    {
                        break;
                    }
                    Release(ref _lister);
                    failures++;
                    SetLink(false, error);
                }

                // Back off up to 60 s while the server is unreachable.
                int wait = error == null ? _options.IntervalSeconds : Math.Min(60, Math.Max(_options.IntervalSeconds, 5 * failures));
                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(Math.Max(1, wait)), token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
            Release(ref _lister);
        }

        private async Task<bool> ScanAsync(FtpClient client, string directory, int depth, List<RemoteEntry> found, CancellationToken token)
        {
            List<RemoteEntry> entries;
            try
            {
                entries = await client.ListAsync(directory);
            }
            catch (FtpException ex)
            {
                if (depth == 0)
                {
                    throw new IOException("Folder remote " + directory + " tidak bisa dibaca: " + ex.Message);
                }
                EventSink.Log("warn", "Subfolder " + directory + " dilewati: " + ex.Message);
                return false;
            }

            bool complete = true;
            foreach (RemoteEntry entry in entries)
            {
                if (token.IsCancellationRequested)
                {
                    return false;
                }
                if (entry.IsDirectory)
                {
                    if (_options.Recursive && depth < _options.MaxDepth)
                    {
                        complete &= await ScanAsync(client, entry.FullPath, depth + 1, found, token);
                    }
                }
                else if (HasWantedExtension(entry.Name))
                {
                    found.Add(entry);
                }
            }
            return complete;
        }

        /// <summary>
        /// Queues files that are new and whose size did not change since the previous scan
        /// (so files still being written on the server are not taken half-way).
        /// </summary>
        private void Enqueue(List<RemoteEntry> found, bool complete)
        {
            var sizes = new Dictionary<string, long>(StringComparer.Ordinal);
            var present = new HashSet<string>(StringComparer.Ordinal);
            int added = 0;
            lock (_sync)
            {
                var busyCodes = new HashSet<string>(_inFlight.Values, StringComparer.OrdinalIgnoreCase);
                busyCodes.Remove(string.Empty);
                foreach (RemoteEntry entry in found)
                {
                    string path = entry.FullPath;
                    string key = StateKey(path, entry.Size);
                    present.Add(key);
                    sizes[path] = entry.Size;
                    if (_done.Contains(key) || _inFlight.ContainsKey(path))
                    {
                        continue;
                    }
                    DateTime retryAfter;
                    if (_retryAfter.TryGetValue(path, out retryAfter) && retryAfter > DateTime.UtcNow)
                    {
                        continue;
                    }
                    long previous;
                    if (!_lastSizes.TryGetValue(path, out previous) || previous != entry.Size)
                    {
                        continue;
                    }
                    // Only one file per code at a time (list is sorted, so the oldest goes first);
                    // the others wait for the next scan and then become duplicates.
                    string code = CodeOf(entry.Name);
                    if (code.Length > 0 && !busyCodes.Add(code))
                    {
                        continue;
                    }
                    if (_inFlight.TryAdd(path, code))
                    {
                        _queue.Enqueue(entry);
                        added++;
                    }
                }
                _lastSizes = sizes;

                // Forget files that disappeared from the server so the state file stays small.
                if (complete)
                {
                    if (_done.RemoveWhere(k => !present.Contains(k)) > 0)
                    {
                        _stateDirty = true;
                    }
                    foreach (string gone in new List<string>(_failures.Keys))
                    {
                        if (!sizes.ContainsKey(gone))
                        {
                            _failures.Remove(gone);
                            _retryAfter.Remove(gone);
                        }
                    }
                }
            }
            if (added > 0)
            {
                _queued.Release(added);
            }
        }

        private async Task WorkerLoopAsync(CancellationToken token)
        {
            FtpClient client = null;
            while (true)
            {
                bool gotItem;
                try
                {
                    gotItem = await _queued.WaitAsync(TimeSpan.FromSeconds(60), token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                if (!gotItem)
                {
                    // Idle: close the connection instead of letting the server time it out.
                    Release(ref client);
                    continue;
                }

                RemoteEntry entry;
                if (!_queue.TryDequeue(out entry))
                {
                    continue;
                }

                string error = null;
                for (int attempt = 1; attempt <= 2; attempt++)
                {
                    error = null;
                    try
                    {
                        if (client == null || !client.IsConnected)
                        {
                            Release(ref client);
                            client = await Connect();
                        }
                        await DownloadAsync(client, entry);
                        break;
                    }
                    catch (Exception ex)
                    {
                        error = ex.Message;
                    }
                    Release(ref client);
                    if (token.IsCancellationRequested)
                    {
                        break;
                    }
                }

                if (error != null)
                {
                    int wait = RegisterFailure(entry.FullPath);
                    EventSink.Emit("file", "status", "error", "source", "download", "client", _options.Host,
                        "original", entry.Name, "name", null, "path", null, "code", null, "bytes", 0,
                        "message", "Gagal mengambil " + entry.FullPath + ": " + error + " (dicoba lagi dalam " + wait + " detik)");
                }
                string ignored;
                _inFlight.TryRemove(entry.FullPath, out ignored);
            }
            Release(ref client);
        }

        private async Task DownloadAsync(FtpClient client, RemoteEntry entry)
        {
            string tempPath = _processor.CreateTempPath();
            long bytes;
            try
            {
                using (var file = new FileStream(tempPath, FileMode.CreateNew, FileAccess.Write, FileShare.None, AsyncUtil.BufferSize, true))
                {
                    bytes = await client.DownloadAsync(entry.Directory, entry.Name, file);
                }
            }
            catch
            {
                PhotoProcessor.TryDelete(tempPath);
                throw;
            }

            PhotoResult result = _processor.Complete(tempPath, entry.Name);
            if (result.Status == PhotoStatus.Error)
            {
                // Local problem (e.g. disk): keep the file on the server and retry next scan.
                PhotoProcessor.TryDelete(tempPath);
                int wait = RegisterFailure(entry.FullPath);
                EventSink.Emit("file", "status", "error", "source", "download", "client", _options.Host,
                    "original", entry.Name, "name", null, "path", null, "code", null, "bytes", bytes,
                    "message", result.Message + " (dicoba lagi dalam " + wait + " detik)");
                return;
            }

            lock (_sync)
            {
                _done.Add(StateKey(entry.FullPath, entry.Size));
                _stateDirty = true;
                _failures.Remove(entry.FullPath);
                _retryAfter.Remove(entry.FullPath);
            }
            EmitFileEvent(result, bytes);

            if (_options.DeleteAfterDownload)
            {
                try
                {
                    await client.DeleteAsync(entry.Directory, entry.Name);
                }
                catch (FtpException ex)
                {
                    EventSink.Log("warn", "File sudah diambil tapi gagal dihapus di server: " + entry.FullPath + " (" + ex.Message + ")");
                }
            }
        }

        /// <summary>Remembers a failed file and returns how many seconds to wait before retrying it.</summary>
        private int RegisterFailure(string path)
        {
            lock (_sync)
            {
                int count;
                _failures.TryGetValue(path, out count);
                count++;
                _failures[path] = count;
                int wait = Math.Min(600, 15 * count * count);
                _retryAfter[path] = DateTime.UtcNow.AddSeconds(wait);
                return wait;
            }
        }

        private void EmitFileEvent(PhotoResult result, long bytes)
        {
            string status;
            switch (result.Status)
            {
                case PhotoStatus.Saved: status = "saved"; break;
                case PhotoStatus.Duplicate: status = "duplicate"; break;
                default: status = "unmatched"; break;
            }
            EventSink.Emit("file", "status", status, "source", "download", "client", _options.Host,
                "original", result.OriginalName, "name", result.NewName, "path", result.FinalPath,
                "code", result.Code, "bytes", bytes, "message", result.Message, "previous", null);
        }

        private static string CodeOf(string name)
        {
            ParsedPhotoName parsed;
            return PhotoProcessor.TryParse(name, out parsed) ? parsed.Code : string.Empty;
        }

        private bool HasWantedExtension(string name)
        {
            if (_options.Extensions == null || _options.Extensions.Length == 0)
            {
                return true;
            }
            string ext = Path.GetExtension(name).TrimStart('.');
            foreach (string wanted in _options.Extensions)
            {
                if (string.Equals(ext, wanted, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
            return false;
        }

        private void ChangeConnections(int delta)
        {
            int count = Interlocked.Add(ref _connections, delta);
            EventSink.Emit("connections", "count", count);
        }

        private void SetLink(bool up, string error)
        {
            lock (_sync)
            {
                if (up == _linkUp && up)
                {
                    return;
                }
                _linkUp = up;
            }
            if (up)
            {
                EventSink.Log("info", "Terhubung ke server FTP " + Describe());
            }
            else
            {
                EventSink.Log("error", "Tidak bisa terhubung ke server FTP " + Describe() + ": " + error + ". Mencoba lagi...");
            }
            EventSink.Emit("link", "connected", up, "server", Describe(), "message", error);
        }

        public static string NormalizeDir(string dir)
        {
            string d = string.IsNullOrEmpty(dir) ? "/" : dir.Trim().Replace('\\', '/');
            if (!d.StartsWith("/", StringComparison.Ordinal))
            {
                d = "/" + d;
            }
            return d.Length > 1 ? d.TrimEnd('/') : d;
        }

        private static string StateKey(string path, long size)
        {
            return path + "|" + size.ToString(CultureInfo.InvariantCulture);
        }

        private void LoadState()
        {
            try
            {
                if (!File.Exists(_stateFile))
                {
                    return;
                }
                lock (_sync)
                {
                    foreach (string line in File.ReadAllLines(_stateFile, Encoding.UTF8))
                    {
                        if (line.Length > 0)
                        {
                            _done.Add(line);
                        }
                    }
                }
                EventSink.Log("info", _done.Count + " file di server sudah pernah diambil sebelumnya (tidak diunduh ulang)");
            }
            catch (Exception ex)
            {
                EventSink.Log("warn", "Daftar file yang sudah diambil tidak bisa dibaca: " + ex.Message);
            }
        }

        private void SaveState(bool force)
        {
            string[] lines;
            lock (_sync)
            {
                if (!_stateDirty && !force)
                {
                    return;
                }
                _stateDirty = false;
                lines = new string[_done.Count];
                _done.CopyTo(lines);
            }
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(_stateFile));
                string temp = _stateFile + ".tmp";
                File.WriteAllLines(temp, lines, new UTF8Encoding(false));
                if (File.Exists(_stateFile))
                {
                    File.Delete(_stateFile);
                }
                File.Move(temp, _stateFile);
            }
            catch (Exception ex)
            {
                EventSink.Log("warn", "Daftar file yang sudah diambil tidak bisa disimpan: " + ex.Message);
            }
        }
    }
}
