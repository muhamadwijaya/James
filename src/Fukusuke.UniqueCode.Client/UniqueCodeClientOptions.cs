using System.ComponentModel.DataAnnotations;

namespace Fukusuke.UniqueCode.Client;

/// <summary>
/// Configuration for <see cref="UniqueCodeClient"/>.
/// </summary>
/// <remarks>
/// <see cref="BaseUrl"/> and <see cref="ApiKey"/> differ between the development
/// and production environments and should always be supplied via configuration
/// (never hard-coded), as noted in the API documentation.
/// </remarks>
public sealed class UniqueCodeClientOptions
{
    /// <summary>Configuration section name used by the console/host bindings.</summary>
    public const string SectionName = "UniqueCodeApi";

    /// <summary>Maximum number of codes that a single request-unique-code call may ask for.</summary>
    public const int MaxRequestCodesPerCall = 500_000;

    /// <summary>Maximum number of confirmations a single confirm-unique-code call may carry.</summary>
    public const int MaxConfirmCodesPerCall = 200_000;

    /// <summary>Base URL of the loyalty API, e.g. <c>https://devloyaltyapi.wingscorp.com</c>.</summary>
    [Required]
    public string BaseUrl { get; set; } = "https://devloyaltyapi.wingscorp.com";

    /// <summary>API key sent in the <c>x-api-key</c> header.</summary>
    [Required]
    public string ApiKey { get; set; } = string.Empty;

    /// <summary>
    /// Request timeout. Defaults to 5 minutes because a single call can move up to
    /// half a million codes.
    /// </summary>
    public TimeSpan Timeout { get; set; } = TimeSpan.FromMinutes(5);

    internal void Validate()
    {
        if (string.IsNullOrWhiteSpace(BaseUrl))
        {
            throw new InvalidOperationException($"{nameof(UniqueCodeClientOptions)}.{nameof(BaseUrl)} must be configured.");
        }

        if (!Uri.TryCreate(BaseUrl, UriKind.Absolute, out _))
        {
            throw new InvalidOperationException($"{nameof(UniqueCodeClientOptions)}.{nameof(BaseUrl)} must be an absolute URL. Got: '{BaseUrl}'.");
        }

        if (string.IsNullOrWhiteSpace(ApiKey))
        {
            throw new InvalidOperationException($"{nameof(UniqueCodeClientOptions)}.{nameof(ApiKey)} must be configured (x-api-key).");
        }
    }
}
