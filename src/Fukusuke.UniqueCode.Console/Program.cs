using Fukusuke.UniqueCode.Client;
using Fukusuke.UniqueCode.Client.Models;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// -----------------------------------------------------------------------------
// FUKUSUKE Unique Code - Vendor Print : demo console
//
// Usage:
//   dotnet run --project src/Fukusuke.UniqueCode.Console -- request [eventId] [vendorId] [materialId] [quantity]
//   dotnet run --project src/Fukusuke.UniqueCode.Console -- confirm  [eventId] [vendorId] [batchId] [code] [yyyy-MM-dd]
//
// Configuration (appsettings.json or environment variables):
//   UniqueCodeApi__BaseUrl   e.g. https://devloyaltyapi.wingscorp.com
//   UniqueCodeApi__ApiKey    the x-api-key value
// Never commit real keys; supply them via environment/secret manager.
//
// Note: positional args (the verb + values) are parsed by this program, so they
// are intentionally NOT passed to the host configuration (which would reject
// non "key=value" tokens). API settings come from appsettings.json + env vars.
// -----------------------------------------------------------------------------

var builder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
{
    // Resolve appsettings.json next to the built binary, not the current directory,
    // so the demo works from anywhere. Args are omitted on purpose (see note above).
    ContentRootPath = AppContext.BaseDirectory,
});
// The default host configuration already loads appsettings.json and environment
// variables; that is where UniqueCodeApi:BaseUrl / ApiKey are read from.
builder.Services.AddUniqueCodeClient(builder.Configuration);

using var host = builder.Build();

var logger = host.Services.GetRequiredService<ILoggerFactory>().CreateLogger("Demo");
var client = host.Services.GetRequiredService<IUniqueCodeClient>();

var verb = args.Length > 0 ? args[0].ToLowerInvariant() : "help";

try
{
    switch (verb)
    {
        case "request":
            await RunRequestAsync(client, args, logger);
            break;

        case "confirm":
            await RunConfirmAsync(client, args, logger);
            break;

        default:
            PrintUsage();
            break;
    }

    return 0;
}
catch (UniqueCodeApiException ex)
{
    logger.LogError("API error {StatusCode}: {ApiMessage}", (int)ex.StatusCode, ex.ApiMessage);
    if (ex.ConfirmData is not null)
    {
        logger.LogError(
            "  status={Status} totalConfirmed={Total}", ex.ConfirmData.Status, ex.ConfirmData.TotalConfirmed);
    }
    return 1;
}
catch (ArgumentException ex)
{
    logger.LogError("Invalid input: {Message}", ex.Message);
    PrintUsage();
    return 2;
}

static async Task RunRequestAsync(IUniqueCodeClient client, string[] args, ILogger logger)
{
    // request [eventId] [vendorId] [materialId] [quantity]
    var eventId = ArgInt(args, 1, 13);
    var vendorId = ArgInt(args, 2, 6);
    var materialId = ArgString(args, 3, "000001");
    var quantity = ArgInt(args, 4, 2);

    var request = new RequestUniqueCodeRequest
    {
        EventId = eventId,
        VendorId = vendorId,
        Materials =
        {
            new MaterialRequest { MaterialId = materialId, PrizeId = null, Quantity = quantity },
        },
    };

    logger.LogInformation(
        "POST request-unique-code  event={EventId} vendor={VendorId} material={MaterialId} qty={Quantity}",
        eventId, vendorId, materialId, quantity);

    var response = await client.RequestUniqueCodesAsync(request);

    Console.WriteLine($"message : {response.Message}");
    if (response.Data is { } data)
    {
        Console.WriteLine($"batchId : {data.BatchId}");
        Console.WriteLine($"sendDate: {data.SendDate:o}");
        foreach (var m in data.Materials)
        {
            Console.WriteLine($"  material {m.MaterialId} ({m.MaterialName}) -> {m.RequestedCodes} code(s)");
            foreach (var code in m.Codes)
            {
                Console.WriteLine($"    {code}");
            }
        }
    }
}

static async Task RunConfirmAsync(IUniqueCodeClient client, string[] args, ILogger logger)
{
    // confirm [eventId] [vendorId] [batchId] [code] [yyyy-MM-dd]
    var eventId = ArgInt(args, 1, 1);
    var vendorId = ArgInt(args, 2, 3);
    var batchId = ArgString(args, 3, "1");
    var code = ArgString(args, 4, "ABC123");
    var date = args.Length > 5 && DateOnly.TryParse(args[5], out var parsed)
        ? parsed
        : DateOnly.FromDateTime(DateTime.UtcNow);

    var request = new ConfirmUniqueCodeRequest
    {
        EventId = eventId,
        VendorId = vendorId,
        Confirmations =
        {
            new Confirmation { BatchId = batchId, Code = code, Date = date },
        },
    };

    logger.LogInformation(
        "POST confirm-unique-code  event={EventId} vendor={VendorId} batch={BatchId} code={Code} date={Date:yyyy-MM-dd}",
        eventId, vendorId, batchId, code, date);

    var response = await client.ConfirmUniqueCodesAsync(request);

    Console.WriteLine($"message : {response.Message}");
    Console.WriteLine($"logId   : {response.LogId}");
    if (response.Data is { } data)
    {
        Console.WriteLine($"status         : {data.Status}");
        Console.WriteLine($"totalConfirmed : {data.TotalConfirmed}");
        if (data.FailedCodes is { Count: > 0 } failed)
        {
            Console.WriteLine($"failedCodes    : {string.Join(", ", failed)}");
        }
    }
}

static void PrintUsage()
{
    Console.WriteLine(
        """
        FUKUSUKE Unique Code - Vendor Print demo

        Commands:
          request [eventId] [vendorId] [materialId] [quantity]
              Request unique codes for a material/SKU.
              Example: request 13 6 000001 2

          confirm [eventId] [vendorId] [batchId] [code] [yyyy-MM-dd]
              Confirm a printed unique code.
              Example: confirm 1 3 1 ABC123 2025-10-29

        Configuration (appsettings.json or env vars):
          UniqueCodeApi__BaseUrl   base URL of the loyalty API
          UniqueCodeApi__ApiKey    the x-api-key value
        """);
}

static int ArgInt(string[] args, int index, int fallback)
    => args.Length > index && int.TryParse(args[index], out var value) ? value : fallback;

static string ArgString(string[] args, int index, string fallback)
    => args.Length > index ? args[index] : fallback;
