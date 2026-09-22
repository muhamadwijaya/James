using System.Text.Json.Serialization;

namespace Fukusuke.UniqueCode.Client.Models;

/// <summary>
/// Generic envelope returned by every endpoint of the Unique Code - Vendor Print API.
/// The API always responds with a <c>message</c> and a <c>data</c> payload
/// (which may be <c>null</c> on error cases).
/// </summary>
/// <typeparam name="TData">Type of the <c>data</c> payload.</typeparam>
public sealed class ApiResponse<TData>
{
    /// <summary>Human readable status message, e.g. "Success" or "Event not found".</summary>
    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;

    /// <summary>Response payload. May be <c>null</c> for error responses.</summary>
    [JsonPropertyName("data")]
    public TData? Data { get; set; }

    /// <summary>
    /// Optional log identifier. Present on the confirm-unique-code responses
    /// (both success and the "no valid codes" error case).
    /// </summary>
    [JsonPropertyName("logId")]
    public string? LogId { get; set; }
}
