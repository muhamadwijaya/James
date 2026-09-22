using System.Text.Json.Serialization;
using Fukusuke.UniqueCode.Client.Json;

namespace Fukusuke.UniqueCode.Client.Models;

/// <summary>
/// Request body for <c>POST /v1/unique-code-prize/confirm-unique-code</c>.
/// Confirms to the loyalty platform which codes were actually printed by the vendor.
/// </summary>
/// <remarks>
/// A single call may confirm at most 200,000 codes. Use the batched client helper
/// to split larger workloads automatically.
/// </remarks>
public sealed class ConfirmUniqueCodeRequest
{
    /// <summary>Identifier of the event the codes belong to.</summary>
    [JsonPropertyName("eventId")]
    public int EventId { get; set; }

    /// <summary>Identifier of the printing vendor confirming the codes.</summary>
    [JsonPropertyName("vendorId")]
    public int VendorId { get; set; }

    /// <summary>The codes being confirmed as printed.</summary>
    [JsonPropertyName("confirmations")]
    public List<Confirmation> Confirmations { get; set; } = new();
}

/// <summary>A single code confirmation entry.</summary>
public sealed class Confirmation
{
    /// <summary>Batch identifier the code was issued under.</summary>
    [JsonPropertyName("batchId")]
    public string BatchId { get; set; } = string.Empty;

    /// <summary>The unique code that was printed.</summary>
    [JsonPropertyName("code")]
    public string Code { get; set; } = string.Empty;

    /// <summary>Date the code was printed/confirmed (serialized as yyyy-MM-dd).</summary>
    [JsonPropertyName("date")]
    [JsonConverter(typeof(DateOnlyJsonConverter))]
    public DateOnly Date { get; set; }
}
