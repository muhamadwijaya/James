using System.Net;
using System.Text;
using System.Text.Json;
using Fukusuke.UniqueCode.Client.Json;
using Fukusuke.UniqueCode.Client.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Fukusuke.UniqueCode.Client;

/// <summary>
/// Default <see cref="IUniqueCodeClient"/> implementation backed by <see cref="HttpClient"/>.
/// </summary>
public sealed class UniqueCodeClient : IUniqueCodeClient
{
    internal const string RequestUniqueCodePath = "/v1/unique-code-prize/request-unique-code";
    internal const string ConfirmUniqueCodePath = "/v1/unique-code-prize/confirm-unique-code";
    internal const string ApiKeyHeader = "x-api-key";

    private static readonly JsonSerializerOptions JsonOptions = CreateJsonOptions();

    private readonly HttpClient _httpClient;
    private readonly UniqueCodeClientOptions _options;
    private readonly ILogger<UniqueCodeClient> _logger;

    public UniqueCodeClient(
        HttpClient httpClient,
        IOptions<UniqueCodeClientOptions> options,
        ILogger<UniqueCodeClient>? logger = null)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _options = (options ?? throw new ArgumentNullException(nameof(options))).Value;
        _logger = logger ?? Microsoft.Extensions.Logging.Abstractions.NullLogger<UniqueCodeClient>.Instance;

        _options.Validate();
        ConfigureHttpClient();
    }

    internal static JsonSerializerOptions CreateJsonOptions()
    {
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web)
        {
            DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.Never,
        };
        options.Converters.Add(new DateOnlyJsonConverter());
        return options;
    }

    private void ConfigureHttpClient()
    {
        // BaseAddress must end with a slash for relative paths (with a leading '/') to combine correctly.
        if (_httpClient.BaseAddress is null)
        {
            var baseUrl = _options.BaseUrl.EndsWith('/') ? _options.BaseUrl : _options.BaseUrl + "/";
            _httpClient.BaseAddress = new Uri(baseUrl, UriKind.Absolute);
        }

        if (_httpClient.Timeout == Timeout.InfiniteTimeSpan || _httpClient.Timeout == TimeSpan.FromSeconds(100))
        {
            // Only override the framework default (100s); respect an explicitly configured handler timeout.
            _httpClient.Timeout = _options.Timeout;
        }

        _httpClient.DefaultRequestHeaders.Accept.Clear();
        _httpClient.DefaultRequestHeaders.Accept.Add(
            new System.Net.Http.Headers.MediaTypeWithQualityHeaderValue("application/json"));

        if (!_httpClient.DefaultRequestHeaders.Contains(ApiKeyHeader))
        {
            _httpClient.DefaultRequestHeaders.Add(ApiKeyHeader, _options.ApiKey);
        }
    }

    /// <inheritdoc />
    public async Task<ApiResponse<RequestUniqueCodeData>> RequestUniqueCodesAsync(
        RequestUniqueCodeRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (request.Materials is null || request.Materials.Count == 0)
        {
            throw new ArgumentException("At least one material must be requested.", nameof(request));
        }

        long total = 0;
        foreach (var material in request.Materials)
        {
            if (string.IsNullOrWhiteSpace(material.MaterialId))
            {
                throw new ArgumentException("Every material must have a non-empty materialId.", nameof(request));
            }

            if (material.Quantity <= 0)
            {
                throw new ArgumentException(
                    $"Material '{material.MaterialId}' must have a positive quantity.", nameof(request));
            }

            total += material.Quantity;
        }

        if (total > UniqueCodeClientOptions.MaxRequestCodesPerCall)
        {
            throw new ArgumentException(
                $"A single request-unique-code call may ask for at most " +
                $"{UniqueCodeClientOptions.MaxRequestCodesPerCall:N0} codes, but {total:N0} were requested. " +
                $"Use {nameof(RequestUniqueCodesBatchedAsync)} to split the workload.",
                nameof(request));
        }

        _logger.LogInformation(
            "Requesting {Total} unique code(s) for event {EventId}, vendor {VendorId} across {MaterialCount} material(s).",
            total, request.EventId, request.VendorId, request.Materials.Count);

        return await SendAsync<RequestUniqueCodeData>(
            RequestUniqueCodePath, request, cancellationToken).ConfigureAwait(false);
    }

    /// <inheritdoc />
    public async Task<IReadOnlyList<ApiResponse<RequestUniqueCodeData>>> RequestUniqueCodesBatchedAsync(
        RequestUniqueCodeRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (request.Materials is null || request.Materials.Count == 0)
        {
            throw new ArgumentException("At least one material must be requested.", nameof(request));
        }

        var responses = new List<ApiResponse<RequestUniqueCodeData>>();
        foreach (var batch in BatchMaterials(request.Materials, UniqueCodeClientOptions.MaxRequestCodesPerCall))
        {
            var batchRequest = new RequestUniqueCodeRequest
            {
                EventId = request.EventId,
                VendorId = request.VendorId,
                Materials = batch,
            };

            responses.Add(await RequestUniqueCodesAsync(batchRequest, cancellationToken).ConfigureAwait(false));
        }

        return responses;
    }

    /// <inheritdoc />
    public async Task<ApiResponse<ConfirmUniqueCodeData>> ConfirmUniqueCodesAsync(
        ConfirmUniqueCodeRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (request.Confirmations is null || request.Confirmations.Count == 0)
        {
            throw new ArgumentException("At least one confirmation must be supplied.", nameof(request));
        }

        if (request.Confirmations.Count > UniqueCodeClientOptions.MaxConfirmCodesPerCall)
        {
            throw new ArgumentException(
                $"A single confirm-unique-code call may confirm at most " +
                $"{UniqueCodeClientOptions.MaxConfirmCodesPerCall:N0} codes, but {request.Confirmations.Count:N0} were supplied. " +
                $"Use {nameof(ConfirmUniqueCodesBatchedAsync)} to split the workload.",
                nameof(request));
        }

        _logger.LogInformation(
            "Confirming {Count} unique code(s) for event {EventId}, vendor {VendorId}.",
            request.Confirmations.Count, request.EventId, request.VendorId);

        return await SendAsync<ConfirmUniqueCodeData>(
            ConfirmUniqueCodePath, request, cancellationToken).ConfigureAwait(false);
    }

    /// <inheritdoc />
    public async Task<IReadOnlyList<ApiResponse<ConfirmUniqueCodeData>>> ConfirmUniqueCodesBatchedAsync(
        ConfirmUniqueCodeRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (request.Confirmations is null || request.Confirmations.Count == 0)
        {
            throw new ArgumentException("At least one confirmation must be supplied.", nameof(request));
        }

        var responses = new List<ApiResponse<ConfirmUniqueCodeData>>();
        for (var offset = 0; offset < request.Confirmations.Count; offset += UniqueCodeClientOptions.MaxConfirmCodesPerCall)
        {
            var chunk = request.Confirmations
                .Skip(offset)
                .Take(UniqueCodeClientOptions.MaxConfirmCodesPerCall)
                .ToList();

            var chunkRequest = new ConfirmUniqueCodeRequest
            {
                EventId = request.EventId,
                VendorId = request.VendorId,
                Confirmations = chunk,
            };

            responses.Add(await ConfirmUniqueCodesAsync(chunkRequest, cancellationToken).ConfigureAwait(false));
        }

        return responses;
    }

    /// <summary>
    /// Splits materials into batches whose total quantity does not exceed <paramref name="maxPerBatch"/>.
    /// A single material may never exceed the limit on its own.
    /// </summary>
    internal static IEnumerable<List<MaterialRequest>> BatchMaterials(
        IReadOnlyList<MaterialRequest> materials, int maxPerBatch)
    {
        var current = new List<MaterialRequest>();
        long currentTotal = 0;

        foreach (var material in materials)
        {
            if (material.Quantity > maxPerBatch)
            {
                throw new ArgumentException(
                    $"Material '{material.MaterialId}' requests {material.Quantity:N0} codes, which exceeds the " +
                    $"per-call limit of {maxPerBatch:N0}. Split this material into smaller quantities.");
            }

            if (currentTotal + material.Quantity > maxPerBatch && current.Count > 0)
            {
                yield return current;
                current = new List<MaterialRequest>();
                currentTotal = 0;
            }

            current.Add(material);
            currentTotal += material.Quantity;
        }

        if (current.Count > 0)
        {
            yield return current;
        }
    }

    private async Task<ApiResponse<TData>> SendAsync<TData>(
        string path, object body, CancellationToken cancellationToken)
    {
        // Serialize against the runtime type so all request properties are emitted
        // (JsonContent.Create/Serialize<object> would use the declared type).
        var json = JsonSerializer.Serialize(body, body.GetType(), JsonOptions);
        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        using var httpRequest = new HttpRequestMessage(HttpMethod.Post, path) { Content = content };

        using var httpResponse = await _httpClient
            .SendAsync(httpRequest, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
            .ConfigureAwait(false);

        var rawBody = await httpResponse.Content
            .ReadAsStringAsync(cancellationToken)
            .ConfigureAwait(false);

        if (httpResponse.IsSuccessStatusCode)
        {
            var parsed = Deserialize<ApiResponse<TData>>(rawBody);
            if (parsed is null)
            {
                throw new UniqueCodeApiException(
                    httpResponse.StatusCode,
                    "The API returned an empty or unparseable success body.",
                    rawBody);
            }

            return parsed;
        }

        throw BuildApiException(httpResponse.StatusCode, rawBody);
    }

    private UniqueCodeApiException BuildApiException(HttpStatusCode statusCode, string rawBody)
    {
        string message = $"HTTP {(int)statusCode}";
        ConfirmUniqueCodeData? confirmData = null;

        // Error bodies share the { message, data, logId? } envelope. data may be null,
        // or (for the confirm "no valid codes" case) a ConfirmUniqueCodeData payload.
        try
        {
            using var document = JsonDocument.Parse(rawBody);
            var root = document.RootElement;

            if (root.TryGetProperty("message", out var messageElement) &&
                messageElement.ValueKind == JsonValueKind.String)
            {
                message = messageElement.GetString() ?? message;
            }

            if (root.TryGetProperty("data", out var dataElement) &&
                dataElement.ValueKind == JsonValueKind.Object)
            {
                confirmData = dataElement.Deserialize<ConfirmUniqueCodeData>(JsonOptions);
            }
        }
        catch (JsonException)
        {
            // Non-JSON error body (e.g. a gateway HTML page); keep the raw body for diagnostics.
        }

        _logger.LogWarning(
            "Unique Code API error {StatusCode}: {Message}", (int)statusCode, message);

        return new UniqueCodeApiException(statusCode, message, rawBody, confirmData);
    }

    private static TValue? Deserialize<TValue>(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return default;
        }

        try
        {
            return JsonSerializer.Deserialize<TValue>(json, JsonOptions);
        }
        catch (JsonException ex)
        {
            throw new UniqueCodeApiException(
                HttpStatusCode.OK,
                "Failed to parse the API response body as JSON.",
                json,
                innerException: ex);
        }
    }
}
