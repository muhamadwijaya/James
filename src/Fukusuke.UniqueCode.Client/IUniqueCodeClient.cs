using Fukusuke.UniqueCode.Client.Models;

namespace Fukusuke.UniqueCode.Client;

/// <summary>
/// Typed client for the FUKUSUKE "Unique Code - Vendor Print" loyalty API.
/// </summary>
public interface IUniqueCodeClient
{
    /// <summary>
    /// Requests (reserves and generates) unique codes for the given materials in a
    /// single API call. The total quantity across all materials must not exceed
    /// <see cref="UniqueCodeClientOptions.MaxRequestCodesPerCall"/> (500,000).
    /// </summary>
    /// <exception cref="ArgumentException">The request is empty or exceeds the per-call limit.</exception>
    /// <exception cref="UniqueCodeApiException">The API returned an error response.</exception>
    Task<ApiResponse<RequestUniqueCodeData>> RequestUniqueCodesAsync(
        RequestUniqueCodeRequest request,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Requests unique codes, automatically splitting the materials into multiple
    /// API calls so that no call exceeds the 500,000-code per-hit limit.
    /// Returns one response per underlying call, in order.
    /// </summary>
    /// <exception cref="ArgumentException">A single material's quantity exceeds the per-call limit.</exception>
    /// <exception cref="UniqueCodeApiException">The API returned an error response.</exception>
    Task<IReadOnlyList<ApiResponse<RequestUniqueCodeData>>> RequestUniqueCodesBatchedAsync(
        RequestUniqueCodeRequest request,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Confirms printed unique codes in a single API call. The number of
    /// confirmations must not exceed
    /// <see cref="UniqueCodeClientOptions.MaxConfirmCodesPerCall"/> (200,000).
    /// </summary>
    /// <exception cref="ArgumentException">The request is empty or exceeds the per-call limit.</exception>
    /// <exception cref="UniqueCodeApiException">
    /// The API returned an error response, including the 400 "No valid unique codes found" case.
    /// </exception>
    Task<ApiResponse<ConfirmUniqueCodeData>> ConfirmUniqueCodesAsync(
        ConfirmUniqueCodeRequest request,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Confirms printed unique codes, automatically splitting confirmations into
    /// chunks of at most 200,000 per API call. Returns one response per call, in order.
    /// </summary>
    /// <exception cref="UniqueCodeApiException">The API returned an error response.</exception>
    Task<IReadOnlyList<ApiResponse<ConfirmUniqueCodeData>>> ConfirmUniqueCodesBatchedAsync(
        ConfirmUniqueCodeRequest request,
        CancellationToken cancellationToken = default);
}
