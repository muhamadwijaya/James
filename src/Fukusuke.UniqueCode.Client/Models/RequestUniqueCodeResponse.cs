using System.Text.Json.Serialization;

namespace Fukusuke.UniqueCode.Client.Models;

/// <summary>
/// <c>data</c> payload for a successful <c>request-unique-code</c> call.
/// </summary>
public sealed class RequestUniqueCodeData
{
    /// <summary>Batch identifier for this shipment of codes to the vendor.</summary>
    [JsonPropertyName("batchId")]
    public string BatchId { get; set; } = string.Empty;

    /// <summary>Echoed event identifier.</summary>
    [JsonPropertyName("eventId")]
    public int EventId { get; set; }

    /// <summary>Per-material results, including the generated codes.</summary>
    [JsonPropertyName("materials")]
    public List<MaterialResult> Materials { get; set; } = new();

    /// <summary>Timestamp (with offset) at which the batch was sent to the vendor.</summary>
    [JsonPropertyName("sendDate")]
    public DateTimeOffset? SendDate { get; set; }
}

/// <summary>Generated codes for a single material within a batch.</summary>
public sealed class MaterialResult
{
    /// <summary>Material / SKU identifier.</summary>
    [JsonPropertyName("materialId")]
    public string MaterialId { get; set; } = string.Empty;

    /// <summary>Human readable material/variant name.</summary>
    [JsonPropertyName("materialName")]
    public string? MaterialName { get; set; }

    /// <summary>Prize identifier, or <c>null</c>.</summary>
    [JsonPropertyName("prizeId")]
    public string? PrizeId { get; set; }

    /// <summary>Human readable prize name (empty when there is no prize).</summary>
    [JsonPropertyName("prizeName")]
    public string? PrizeName { get; set; }

    /// <summary>Number of codes that were requested for this material.</summary>
    [JsonPropertyName("requestedCodes")]
    public int RequestedCodes { get; set; }

    /// <summary>The generated unique codes for this material.</summary>
    [JsonPropertyName("codes")]
    public List<string> Codes { get; set; } = new();
}
