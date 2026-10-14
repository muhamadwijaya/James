using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace FtpBackend
{
    internal enum PhotoStatus
    {
        Saved,
        Duplicate,
        Unmatched,
        Error
    }

    internal sealed class PhotoResult
    {
        public PhotoStatus Status;
        public string OriginalName;
        public string NewName;
        public string FinalPath;
        public string Code;
        public string Message;

        /// <summary>
        /// Unmatched file that was not kept: it still sits at <see cref="FinalPath"/> (a temp
        /// file) and the caller must delete it once it is sure no rename will follow.
        /// </summary>
        public bool Held;
    }

    internal sealed class ParsedPhotoName
    {
        public string Code;
        public DateTime Timestamp;
        public string Extension;
    }

    /// <summary>
    /// Renames received photos and keeps only one photo per code.
    ///
    ///   received : "3975 264 812_2026_10_10_00_08_46.jpg"                   -> code "3975264812"
    ///              "https&amp;&amp;&amp;aslibos.com&amp;scan&amp;BXXAXESPP2026_10_14_12_16_53.jpg" -> code "BXXAXESPP"
    ///   saved as : "LINE-ID_YYYYMMDD_HHMMSS_CODE.jpg", e.g. "00001_20261014_121653_BXXAXESPP.jpg"
    ///
    /// The date/time YYYY_MM_DD_HH_MM_SS is found first; the code is the text right before it,
    /// after the last separator (&amp; / \ = ? # _ : ;), so URL prefixes are ignored and the
    /// code may have any length.
    /// </summary>
    internal sealed class PhotoProcessor
    {
        private static readonly Regex IncomingPattern = new Regex(
            @"^(?<prefix>.*?)(?<y>[0-9]{4})[_-](?<mo>[0-9]{2})[_-](?<d>[0-9]{2})[_-](?<h>[0-9]{2})[_-](?<mi>[0-9]{2})[_-](?<s>[0-9]{2})(?<rest>[^.]*)(?<ext>\.[A-Za-z0-9]+)?\s*$",
            RegexOptions.CultureInvariant);

        private static readonly char[] CodeSeparators = { '&', '/', '\\', '=', '?', '#', '_', ':', ';' };

        // Files already in the target folder: LINE-ID_YYYYMMDD_HHMMSS_CODE[_n].ext
        private static readonly Regex SavedPattern = new Regex(
            @"^.+_(?<date>[0-9]{8})_(?<time>[0-9]{6})_(?<code>[^_]+?)(?:_[0-9]+)?\.[A-Za-z0-9]+$",
            RegexOptions.CultureInvariant);

        // Same set on every OS, so names built on Linux tests match Windows.
        private static readonly char[] InvalidNameChars = { '\\', '/', ':', '*', '?', '"', '<', '>', '|' };

        private readonly object _sync = new object();
        private readonly DailyTextLog _unmatchedLog;
        private readonly Dictionary<string, DateTime> _seenCodes = new Dictionary<string, DateTime>(StringComparer.OrdinalIgnoreCase);
        private string _lineId;

        public PhotoProcessor(string targetDir, string lineId, bool dedupEnabled, int dedupWindowMinutes, bool keepDuplicates,
            bool keepUnmatched)
        {
            TargetDir = Path.GetFullPath(targetDir);
            IncomingDir = Path.Combine(TargetDir, ".incoming");
            DuplicateDir = Path.Combine(TargetDir, "_duplikat");
            UnmatchedDir = Path.Combine(TargetDir, "_tidak_sesuai");
            LogDir = Path.Combine(TargetDir, "_log");
            _unmatchedLog = new DailyTextLog(LogDir, "tidak_sesuai_", null);
            _lineId = lineId;
            DedupEnabled = dedupEnabled;
            DedupWindowMinutes = dedupWindowMinutes;
            KeepDuplicates = keepDuplicates;
            KeepUnmatched = keepUnmatched;
        }

        public string TargetDir { get; private set; }
        public string IncomingDir { get; private set; }
        public string DuplicateDir { get; private set; }
        public string UnmatchedDir { get; private set; }
        public string LogDir { get; private set; }
        public bool DedupEnabled { get; private set; }
        public int DedupWindowMinutes { get; private set; }
        public bool KeepDuplicates { get; private set; }

        /// <summary>False (default): unmatched photos are not saved, only written to the txt log.</summary>
        public bool KeepUnmatched { get; private set; }

        public string LineId
        {
            get { lock (_sync) { return _lineId; } }
            set { lock (_sync) { _lineId = value; } }
        }

        /// <summary>
        /// Creates the folders, removes leftovers of interrupted uploads and loads the
        /// codes already present in the target folder. Returns the number of known codes.
        /// </summary>
        public int Prepare()
        {
            Directory.CreateDirectory(TargetDir);
            DirectoryInfo incoming = Directory.CreateDirectory(IncomingDir);
            try
            {
                incoming.Attributes |= FileAttributes.Hidden;
            }
            catch (Exception)
            {
            }

            foreach (string leftover in Directory.GetFiles(IncomingDir, "*.part"))
            {
                TryDelete(leftover);
            }

            lock (_sync)
            {
                _seenCodes.Clear();
                if (DedupEnabled)
                {
                    foreach (string path in Directory.EnumerateFiles(TargetDir))
                    {
                        Match m = SavedPattern.Match(Path.GetFileName(path));
                        if (!m.Success)
                        {
                            continue;
                        }
                        DateTime ts;
                        if (DateTime.TryParseExact(m.Groups["date"].Value + m.Groups["time"].Value, "yyyyMMddHHmmss",
                                CultureInfo.InvariantCulture, DateTimeStyles.None, out ts))
                        {
                            Remember(m.Groups["code"].Value, ts);
                        }
                    }
                }
                return _seenCodes.Count;
            }
        }

        public string CreateTempPath()
        {
            Directory.CreateDirectory(IncomingDir);
            return Path.Combine(IncomingDir, Guid.NewGuid().ToString("N") + ".part");
        }

        /// <summary>
        /// Moves a fully received file to its final place. The caller owns
        /// <paramref name="sourcePath"/> again when the result status is Error, or when
        /// <see cref="PhotoResult.Held"/> is set.
        /// </summary>
        public PhotoResult Complete(string sourcePath, string originalName, string client, long bytes)
        {
            var result = new PhotoResult();
            result.OriginalName = originalName;
            try
            {
                ParsedPhotoName parsed;
                if (!TryParse(originalName, out parsed))
                {
                    if (!KeepUnmatched)
                    {
                        PhotoResult logged = RecordUnmatched(originalName, client, bytes);
                        logged.FinalPath = sourcePath;
                        logged.Held = true;
                        return logged;
                    }
                    lock (_sync)
                    {
                        WriteUnmatchedLog(originalName, client, bytes);
                        Directory.CreateDirectory(UnmatchedDir);
                        result.FinalPath = MoveUnique(sourcePath, UnmatchedDir, SanitizeFileName(originalName));
                    }
                    result.NewName = Path.GetFileName(result.FinalPath);
                    result.Status = PhotoStatus.Unmatched;
                    result.Message = "Format nama file tidak sesuai, disimpan ke _tidak_sesuai";
                    return result;
                }

                result.Code = parsed.Code;
                lock (_sync)
                {
                    string newName = BuildName(parsed, _lineId);
                    result.NewName = newName;

                    DateTime previous;
                    if (DedupEnabled && _seenCodes.TryGetValue(parsed.Code, out previous) && IsWithinWindow(previous, parsed.Timestamp))
                    {
                        result.Status = PhotoStatus.Duplicate;
                        result.Message = "Code sudah pernah disimpan";
                        if (KeepDuplicates)
                        {
                            Directory.CreateDirectory(DuplicateDir);
                            result.FinalPath = MoveUnique(sourcePath, DuplicateDir, newName);
                            result.NewName = Path.GetFileName(result.FinalPath);
                        }
                        else
                        {
                            File.Delete(sourcePath);
                        }
                        return result;
                    }

                    Directory.CreateDirectory(TargetDir);
                    result.FinalPath = MoveUnique(sourcePath, TargetDir, newName);
                    result.NewName = Path.GetFileName(result.FinalPath);
                    result.Status = PhotoStatus.Saved;
                    Remember(parsed.Code, parsed.Timestamp);
                }
            }
            catch (Exception ex)
            {
                result.Status = PhotoStatus.Error;
                result.Message = ex.Message;
            }
            return result;
        }

        /// <summary>
        /// Writes an unmatched file name to the daily txt log (_log\tidak_sesuai_yyyy-MM-dd.txt)
        /// without saving the photo.
        /// </summary>
        public PhotoResult RecordUnmatched(string originalName, string client, long bytes)
        {
            var result = new PhotoResult();
            result.OriginalName = originalName;
            result.Status = PhotoStatus.Unmatched;
            try
            {
                string logFile;
                lock (_sync)
                {
                    logFile = WriteUnmatchedLog(originalName, client, bytes);
                }
                result.Message = "Format nama tidak sesuai, foto tidak disimpan (dicatat di _log\\" + Path.GetFileName(logFile) + ")";
            }
            catch (Exception ex)
            {
                result.Message = "Format nama tidak sesuai, foto tidak disimpan (log gagal ditulis: " + ex.Message + ")";
            }
            return result;
        }

        public static bool IsMatch(string fileName)
        {
            ParsedPhotoName ignored;
            return TryParse(fileName, out ignored);
        }

        public static bool TryParse(string fileName, out ParsedPhotoName parsed)
        {
            parsed = null;
            if (string.IsNullOrEmpty(fileName))
            {
                return false;
            }

            Match m = IncomingPattern.Match(fileName);
            if (!m.Success)
            {
                return false;
            }

            string code = ExtractCode(m.Groups["prefix"].Value);
            if (code.Length == 0)
            {
                return false;
            }

            string stamp = m.Groups["y"].Value + m.Groups["mo"].Value + m.Groups["d"].Value +
                           m.Groups["h"].Value + m.Groups["mi"].Value + m.Groups["s"].Value;
            DateTime ts;
            if (!DateTime.TryParseExact(stamp, "yyyyMMddHHmmss", CultureInfo.InvariantCulture, DateTimeStyles.None, out ts))
            {
                return false;
            }

            parsed = new ParsedPhotoName();
            parsed.Code = code;
            parsed.Timestamp = ts;
            parsed.Extension = m.Groups["ext"].Success ? m.Groups["ext"].Value.ToLowerInvariant() : ".jpg";
            return true;
        }

        public static string BuildName(ParsedPhotoName parsed, string lineId)
        {
            return lineId + "_" + parsed.Timestamp.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture) +
                   "_" + parsed.Code + parsed.Extension;
        }

        /// <summary>
        /// Text before the date -> code: "3975 264 812_" -> "3975264812",
        /// "https&amp;&amp;&amp;aslibos.com&amp;scan&amp;BXXAXESPP" -> "BXXAXESPP".
        /// </summary>
        public static string ExtractCode(string prefix)
        {
            string text = prefix ?? string.Empty;
            if (text.IndexOf('%') >= 0)
            {
                try
                {
                    text = Uri.UnescapeDataString(text);
                }
                catch (Exception)
                {
                }
            }
            text = text.TrimEnd('_', '-', ' ', '\t');
            int cut = text.LastIndexOfAny(CodeSeparators);
            if (cut >= 0)
            {
                text = text.Substring(cut + 1);
            }
            return CleanCode(text);
        }

        /// <summary>"3975 264 812" -> "3975264812"</summary>
        public static string CleanCode(string raw)
        {
            var sb = new StringBuilder(raw.Length);
            foreach (char c in raw)
            {
                if (char.IsWhiteSpace(c) || char.IsControl(c) || c == '_' || Array.IndexOf(InvalidNameChars, c) >= 0)
                {
                    continue;
                }
                sb.Append(c);
            }
            return sb.ToString();
        }

        /// <summary>LINE-ID may contain '_' but no spaces or characters Windows forbids.</summary>
        public static string CleanLineId(string raw)
        {
            var sb = new StringBuilder(raw.Length);
            foreach (char c in raw)
            {
                if (char.IsWhiteSpace(c) || char.IsControl(c) || Array.IndexOf(InvalidNameChars, c) >= 0)
                {
                    continue;
                }
                sb.Append(c);
            }
            return sb.ToString();
        }

        public static string SanitizeFileName(string name)
        {
            var sb = new StringBuilder(name == null ? 0 : name.Length);
            if (name != null)
            {
                foreach (char c in name)
                {
                    sb.Append(char.IsControl(c) || Array.IndexOf(InvalidNameChars, c) >= 0 ? '_' : c);
                }
            }
            string cleaned = sb.ToString().Trim().TrimEnd('.');
            if (cleaned.Length == 0)
            {
                cleaned = "file_" + DateTime.Now.ToString("yyyyMMdd_HHmmss_fff", CultureInfo.InvariantCulture);
            }
            return cleaned;
        }

        public static void TryDelete(string path)
        {
            try
            {
                if (!string.IsNullOrEmpty(path) && File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch (Exception)
            {
            }
        }

        private string WriteUnmatchedLog(string originalName, string client, long bytes)
        {
            DateTime now = DateTime.Now;
            string line = now.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture) + " | " +
                          (string.IsNullOrEmpty(client) ? "-" : client) + " | " +
                          bytes.ToString(CultureInfo.InvariantCulture) + " bytes | " + originalName;
            return _unmatchedLog.Write(now, line);
        }

        public void CloseLogs()
        {
            _unmatchedLog.Close();
        }

        private bool IsWithinWindow(DateTime previous, DateTime current)
        {
            if (DedupWindowMinutes <= 0)
            {
                return true;
            }
            return Math.Abs((current - previous).TotalMinutes) < DedupWindowMinutes;
        }

        private void Remember(string code, DateTime timestamp)
        {
            DateTime existing;
            if (!_seenCodes.TryGetValue(code, out existing) || timestamp > existing)
            {
                _seenCodes[code] = timestamp;
            }
        }

        private static string MoveUnique(string source, string dir, string fileName)
        {
            string stem = Path.GetFileNameWithoutExtension(fileName);
            string ext = Path.GetExtension(fileName);
            for (int i = 0; i < 10000; i++)
            {
                string candidate = Path.Combine(dir, i == 0 ? fileName : stem + "_" + i.ToString(CultureInfo.InvariantCulture) + ext);
                if (File.Exists(candidate))
                {
                    continue;
                }
                try
                {
                    File.Move(source, candidate);
                    return candidate;
                }
                catch (IOException)
                {
                    if (!File.Exists(candidate))
                    {
                        throw;
                    }
                }
            }
            throw new IOException("Tidak bisa menentukan nama file unik untuk " + fileName);
        }
    }
}
