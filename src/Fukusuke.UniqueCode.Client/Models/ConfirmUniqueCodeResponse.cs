using System.Text.Json.Serialization;

namespace Fukusuke.UniqueCode.Client.Models;

/// <summary>Status values returned in the confirm-unique-code <c>data.status</c> field.</summary>
public static class ConfirmationStatus
{
    /// <summary>All submitted codes were confirmed.</summary>
    public const string Success = "success";

    /// <summary>Some codes were confirmed and some failed.</summary>
    public const string PartialSuccess = "partial_success";

    /// <summary>No submitted code matched; nothing was confirmed.</summary>
    public const string Failed = "failed";
}

/// <summary>
/// <c>data</c> payload for a <c>confirm-unique-code</c> call. The same shape is used
/// for full success, partial success, and the "no valid codes" failure case.
/// </summary>
public sealed class ConfirmUniqueCodeData
{
    /// <summary>
    /// Outcome status: one of the <see cref="ConfirmationStatus"/> constants
    /// (<c>success</c>, <c>partial_success</c>, or <c>failed</c>).
    /// </summary>
    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    /// <summary>Number of codes that were successfully confirmed.</summary>
    [JsonPropertyName("totalConfirmed")]
    public long TotalConfirmed { get; set; }

    /// <summary>
    /// Codes that could not be confirmed. Present on the partial-success case;
    /// <c>null</c> or empty otherwise.
    /// </summary>
    [JsonPropertyName("failedCodes")]
    public List<string>? FailedCodes { get; set; }
}
