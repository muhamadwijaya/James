using System.Text.Json.Serialization;

namespace Fukusuke.UniqueCode.Client.Models;

/// <summary>
/// Request body for <c>POST /v1/unique-code-prize/request-unique-code</c>.
/// Asks the loyalty platform to generate/reserve unique codes for one or more
/// material variants (SKUs) that will be printed by the vendor.
/// </summary>
/// <remarks>
/// The total number of codes requested in a single call (the sum of
/// <see cref="MaterialRequest.Quantity"/> across all materials) must not
/// exceed 500,000. Use the batched client helpers to split larger workloads.
/// </remarks>
public sealed class RequestUniqueCodeRequest
{
    /// <summary>Identifier of the event the codes belong to.</summary>
    [JsonPropertyName("eventId")]
    public int EventId { get; set; }

    /// <summary>Identifier of the printing vendor the codes are destined for.</summary>
    [JsonPropertyName("vendorId")]
    public int VendorId { get; set; }

    /// <summary>Materials (SKU variants) for which codes are requested.</summary>
    [JsonPropertyName("materials")]
    public List<MaterialRequest> Materials { get; set; } = new();
}

/// <summary>A single material (SKU variant) and how many codes to request for it.</summary>
public sealed class MaterialRequest
{
    /// <summary>Material / SKU identifier, e.g. "000001". Sent as a string (leading zeros are significant).</summary>
    [JsonPropertyName("materialId")]
    public string MaterialId { get; set; } = string.Empty;

    /// <summary>
    /// Prize identifier associated with the material, or <c>null</c> when the
    /// event has no prize attached to this material.
    /// </summary>
    [JsonPropertyName("prizeId")]
    public string? PrizeId { get; set; }

    /// <summary>Number of unique codes requested for this material.</summary>
    [JsonPropertyName("quantity")]
    public int Quantity { get; set; }
}
