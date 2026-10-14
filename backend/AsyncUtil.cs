using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace FtpBackend
{
    internal static class AsyncUtil
    {
        public const int BufferSize = 81920;

        /// <summary>True when <paramref name="task"/> finished within the time limit.</summary>
        public static async Task<bool> WithTimeout(Task task, int seconds)
        {
            using (var cts = new CancellationTokenSource())
            {
                Task delay = Task.Delay(TimeSpan.FromSeconds(seconds), cts.Token);
                Task first = await Task.WhenAny(task, delay);
                cts.Cancel();
                return first == task;
            }
        }

        /// <summary>Copies until end of stream; fails when no data arrives for <paramref name="idleSeconds"/>.</summary>
        public static Task<long> CopyAsync(Stream source, Stream destination, int idleSeconds)
        {
            return CopyAsync(source, destination, idleSeconds, null);
        }

        public static async Task<long> CopyAsync(Stream source, Stream destination, int idleSeconds, TransferReporter progress)
        {
            byte[] buffer = new byte[BufferSize];
            long total = 0;
            while (true)
            {
                Task<int> read = source.ReadAsync(buffer, 0, buffer.Length);
                if (!await WithTimeout(read, idleSeconds))
                {
                    throw new TimeoutException("Tidak ada data selama " + idleSeconds + " detik");
                }
                int count = await read;
                if (count <= 0)
                {
                    break;
                }
                await destination.WriteAsync(buffer, 0, count);
                total += count;
                if (progress != null)
                {
                    progress.Progress(total);
                }
            }
            await destination.FlushAsync();
            return total;
        }
    }

    /// <summary>
    /// Reports one file transfer to the GUI ("Transfer Saat Ini"): progress at most every
    /// 250 ms while running (only for transfers that take that long) and always when done.
    /// </summary>
    internal sealed class TransferReporter
    {
        private static int _nextId;
        private readonly int _id;
        private readonly string _name;
        private readonly string _newName;
        private readonly string _client;
        private readonly long _total;
        private readonly Stopwatch _watch = Stopwatch.StartNew();
        private long _lastEmitMs;

        public TransferReporter(string name, string newName, string client, long total)
        {
            _id = Interlocked.Increment(ref _nextId);
            _name = name;
            _newName = newName;
            _client = client;
            _total = total;
        }

        public void Progress(long bytes)
        {
            long now = _watch.ElapsedMilliseconds;
            if (now - _lastEmitMs >= 250)
            {
                _lastEmitMs = now;
                Emit("progress", bytes);
            }
        }

        public void Done(long bytes)
        {
            Emit("done", bytes);
        }

        public void Failed(long bytes)
        {
            Emit("error", bytes);
        }

        private void Emit(string state, long bytes)
        {
            EventSink.Emit("transfer", "id", _id, "state", state, "name", _name, "new_name", _newName,
                "client", _client, "bytes", bytes, "total", _total, "ms", _watch.ElapsedMilliseconds);
        }
    }
}
