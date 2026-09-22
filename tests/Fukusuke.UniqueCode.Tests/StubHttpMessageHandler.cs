using System.Net;

namespace Fukusuke.UniqueCode.Tests;

/// <summary>
/// Test double that records outgoing requests and returns queued responses.
/// </summary>
public sealed class StubHttpMessageHandler : HttpMessageHandler
{
    private readonly Queue<Func<HttpRequestMessage, HttpResponseMessage>> _responders = new();

    public List<RecordedRequest> Requests { get; } = new();

    public StubHttpMessageHandler EnqueueJson(HttpStatusCode statusCode, string json)
    {
        _responders.Enqueue(_ => new HttpResponseMessage(statusCode)
        {
            Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json"),
        });
        return this;
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var body = request.Content is null
            ? string.Empty
            : await request.Content.ReadAsStringAsync(cancellationToken);

        request.Headers.TryGetValues("x-api-key", out var apiKeyValues);

        Requests.Add(new RecordedRequest(
            request.Method,
            request.RequestUri,
            body,
            apiKeyValues?.FirstOrDefault(),
            request.Headers.Accept.ToString()));

        if (_responders.Count == 0)
        {
            throw new InvalidOperationException("No queued response for request to " + request.RequestUri);
        }

        return _responders.Dequeue().Invoke(request);
    }
}

public sealed record RecordedRequest(
    HttpMethod Method,
    Uri? Uri,
    string Body,
    string? ApiKey,
    string Accept);
