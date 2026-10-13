using System;
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
        public static async Task<long> CopyAsync(Stream source, Stream destination, int idleSeconds)
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
            }
            await destination.FlushAsync();
            return total;
        }
    }
}
