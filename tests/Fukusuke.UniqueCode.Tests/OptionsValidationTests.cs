using Fukusuke.UniqueCode.Client;
using Microsoft.Extensions.Options;
using Xunit;

namespace Fukusuke.UniqueCode.Tests;

public class OptionsValidationTests
{
    [Fact]
    public void Client_Throws_WhenApiKeyMissing()
    {
        var options = Options.Create(new UniqueCodeClientOptions
        {
            BaseUrl = "https://devloyaltyapi.wingscorp.com",
            ApiKey = "",
        });

        Assert.Throws<InvalidOperationException>(() =>
            new UniqueCodeClient(new HttpClient(new StubHttpMessageHandler()), options));
    }

    [Fact]
    public void Client_Throws_WhenBaseUrlNotAbsolute()
    {
        var options = Options.Create(new UniqueCodeClientOptions
        {
            BaseUrl = "not-a-url",
            ApiKey = "key",
        });

        Assert.Throws<InvalidOperationException>(() =>
            new UniqueCodeClient(new HttpClient(new StubHttpMessageHandler()), options));
    }
}
