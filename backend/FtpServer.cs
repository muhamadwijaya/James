using System;
using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;

namespace FtpBackend
{
    internal sealed class ServerOptions
    {
        public IPAddress BindAddress;
        public int Port;
        public string User;
        public string Password;
        public bool AllowAnyLogin;
        public int PassivePortMin;
        public int PassivePortMax;
        public int IdleTimeoutSeconds;
        public int DataTimeoutSeconds;
    }

    /// <summary>
    /// Accepts FTP control connections. Every connection runs as its own
    /// asynchronous session, so many cameras can upload at the same time.
    /// </summary>
    internal sealed class FtpServer
    {
        private readonly ConcurrentDictionary<int, FtpSession> _sessions = new ConcurrentDictionary<int, FtpSession>();
        private readonly object _portSync = new object();
        private TcpListener _listener;
        private Task _acceptTask;
        private int _nextSessionId;
        private int _nextPassiveOffset;
        private int _passiveRangeWarned;
        private volatile bool _stopping;

        public FtpServer(ServerOptions options, PhotoProcessor processor)
        {
            Options = options;
            Processor = processor;
        }

        public ServerOptions Options { get; private set; }
        public PhotoProcessor Processor { get; private set; }

        public bool IsStopping
        {
            get { return _stopping; }
        }

        public void Start()
        {
            _listener = new TcpListener(Options.BindAddress, Options.Port);
            _listener.Start(128);
            _acceptTask = Task.Run(() => AcceptLoopAsync());
        }

        /// <summary>Stops accepting, lets running uploads finish (max ~10 s), then closes everything.</summary>
        public void Stop()
        {
            _stopping = true;
            try
            {
                _listener.Stop();
            }
            catch (Exception)
            {
            }

            foreach (FtpSession session in _sessions.Values)
            {
                session.RequestStop();
            }

            DateTime deadline = DateTime.UtcNow.AddSeconds(10);
            while (!_sessions.IsEmpty && DateTime.UtcNow < deadline)
            {
                Thread.Sleep(50);
            }

            foreach (FtpSession session in _sessions.Values)
            {
                session.Abort();
            }

            try
            {
                if (_acceptTask != null)
                {
                    _acceptTask.Wait(2000);
                }
            }
            catch (Exception)
            {
            }
        }

        /// <summary>Opens a listener for PASV/EPSV inside the configured passive port range.</summary>
        public TcpListener OpenPassiveListener(IPAddress localAddress)
        {
            int min = Options.PassivePortMin;
            int max = Options.PassivePortMax;
            if (min <= 0 || max < min)
            {
                var any = new TcpListener(localAddress, 0);
                any.Start(1);
                return any;
            }

            int count = max - min + 1;
            for (int attempt = 0; attempt < count; attempt++)
            {
                int port;
                lock (_portSync)
                {
                    port = min + _nextPassiveOffset;
                    _nextPassiveOffset = (_nextPassiveOffset + 1) % count;
                }

                var listener = new TcpListener(localAddress, port);
                try
                {
                    listener.Start(1);
                    return listener;
                }
                catch (SocketException)
                {
                    // Port busy, try the next one.
                }
            }

            // Range exhausted (more parallel transfers than ports): an automatic port is
            // better than refusing the photo.
            if (Interlocked.Exchange(ref _passiveRangeWarned, 1) == 0)
            {
                EventSink.Log("warn", "Semua port pasif " + min + "-" + max + " sedang dipakai, memakai port otomatis. Perbesar rentang port pasif.");
            }
            var fallback = new TcpListener(localAddress, 0);
            fallback.Start(1);
            return fallback;
        }

        private async Task AcceptLoopAsync()
        {
            while (!_stopping)
            {
                TcpClient client;
                try
                {
                    client = await _listener.AcceptTcpClientAsync();
                }
                catch (ObjectDisposedException)
                {
                    break;
                }
                catch (InvalidOperationException)
                {
                    break;
                }
                catch (SocketException ex)
                {
                    if (_stopping)
                    {
                        break;
                    }
                    EventSink.Log("warn", "Gagal menerima koneksi: " + ex.Message);
                    continue;
                }

                if (_stopping)
                {
                    client.Close();
                    break;
                }
                StartSession(client);
            }
        }

        private void StartSession(TcpClient client)
        {
            int id = Interlocked.Increment(ref _nextSessionId);
            FtpSession session;
            try
            {
                client.NoDelay = true;
                session = new FtpSession(id, client, this);
            }
            catch (Exception ex)
            {
                client.Close();
                EventSink.Log("warn", "Koneksi ditolak: " + ex.Message);
                return;
            }

            _sessions[id] = session;
            EventSink.Log("info", "Klien terhubung: " + session.Remote);
            EmitConnectionCount();

            Task.Run(() => session.RunAsync()).ContinueWith(t =>
            {
                FtpSession removed;
                _sessions.TryRemove(id, out removed);
                EventSink.Log("info", "Klien terputus: " + session.Remote);
                EmitConnectionCount();
            });
        }

        private void EmitConnectionCount()
        {
            EventSink.Emit("connections", "count", _sessions.Count);
        }
    }
}
