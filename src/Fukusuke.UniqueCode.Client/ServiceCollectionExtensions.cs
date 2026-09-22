using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Fukusuke.UniqueCode.Client;

/// <summary>
/// Dependency-injection helpers for registering <see cref="IUniqueCodeClient"/>.
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Registers <see cref="IUniqueCodeClient"/> using an <see cref="IHttpClientFactory"/>-managed
    /// <see cref="HttpClient"/>, binding options from the <c>UniqueCodeApi</c> configuration section.
    /// </summary>
    public static IHttpClientBuilder AddUniqueCodeClient(
        this IServiceCollection services, IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        services
            .AddOptions<UniqueCodeClientOptions>()
            .Bind(configuration.GetSection(UniqueCodeClientOptions.SectionName))
            .Validate(o =>
            {
                try { o.Validate(); return true; }
                catch { return false; }
            }, "UniqueCodeApi configuration is invalid (check BaseUrl and ApiKey).");

        return services.AddHttpClient<IUniqueCodeClient, UniqueCodeClient>();
    }

    /// <summary>
    /// Registers <see cref="IUniqueCodeClient"/> using an explicit options delegate.
    /// </summary>
    public static IHttpClientBuilder AddUniqueCodeClient(
        this IServiceCollection services, Action<UniqueCodeClientOptions> configure)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configure);

        services
            .AddOptions<UniqueCodeClientOptions>()
            .Configure(configure)
            .Validate(o =>
            {
                try { o.Validate(); return true; }
                catch { return false; }
            }, "UniqueCodeApi configuration is invalid (check BaseUrl and ApiKey).");

        return services.AddHttpClient<IUniqueCodeClient, UniqueCodeClient>();
    }
}
