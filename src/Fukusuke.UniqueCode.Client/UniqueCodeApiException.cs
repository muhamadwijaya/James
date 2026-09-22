using System.Net;
using Fukusuke.UniqueCode.Client.Models;

namespace Fukusuke.UniqueCode.Client;

/// <summary>
/// Thrown when the Unique Code - Vendor Print API returns a non-success HTTP status
/// (e.g. 400 "Event not found", 400 "Unique code habis ...", 500 "Internal server error").
/// </summary>
public sealed class UniqueCodeApiException : Exception
{
    public UniqueCodeApiException(
        HttpStatusCode statusCode,
        string apiMessage,
        string? rawBody,
        ConfirmUniqueCodeData? confirmData = null,
        Exception? innerException = null)
        : base(BuildMessage(statusCode, apiMessage), innerException)
    {
        StatusCode = statusCode;
        ApiMessage = apiMessage;
        RawBody = rawBody;
        ConfirmData = confirmData;
    }

    /// <summary>HTTP status code returned by the API.</summary>
    public HttpStatusCode StatusCode { get; }

    /// <summary>The <c>message</c> field extracted from the API error body.</summary>
    public string ApiMessage { get; }

    /// <summary>The raw, unparsed response body (useful for diagnostics/logging).</summary>
    public string? RawBody { get; }

    /// <summary>
    /// For the confirm endpoint's "No valid unique codes found" (400) case, the
    /// structured <c>data</c> payload (status = <c>failed</c>, totalConfirmed = 0).
    /// <c>null</c> for other errors.
    /// </summary>
    public ConfirmUniqueCodeData? ConfirmData { get; }

    private static string BuildMessage(HttpStatusCode statusCode, string apiMessage)
    {
        var reason = string.IsNullOrWhiteSpace(apiMessage) ? "(no message)" : apiMessage;
        return $"Unique Code API returned {(int)statusCode} {statusCode}: {reason}";
    }
}
