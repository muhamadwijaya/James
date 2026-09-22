using Fukusuke.UniqueCode.Client;
using Microsoft.Extensions.Options;

namespace Fukusuke.UniqueCode.Tests;

/// <summary>Helpers for constructing a <see cref="UniqueCodeClient"/> around a stub handler.</summary>
internal static class TestFactory
{
    public const string BaseUrl = "https://devloyaltyapi.wingscorp.com";
    public const string ApiKey = "D4rmM8Kj+WtKOB8RdL6qMfFneJ6tUTfjT9NswIqZYWs=";

    public static UniqueCodeClient CreateClient(StubHttpMessageHandler handler)
    {
        var httpClient = new HttpClient(handler);
        var options = Options.Create(new UniqueCodeClientOptions
        {
            BaseUrl = BaseUrl,
            ApiKey = ApiKey,
        });

        return new UniqueCodeClient(httpClient, options);
    }
}
