using System.Net;
using System.Text.Json;
using Fukusuke.UniqueCode.Client;
using Fukusuke.UniqueCode.Client.Models;
using Xunit;

namespace Fukusuke.UniqueCode.Tests;

public class ConfirmUniqueCodeTests
{
    private const string FullSuccessBody =
        """
        {
            "message": "All unique codes confirmed successfully",
            "data": { "status": "success", "totalConfirmed": 499997 },
            "logId": "234234"
        }
        """;

    private const string PartialSuccessBody =
        """
        {
            "message": "Confirmation processed with some failures",
            "data": {
                "status": "partial_success",
                "totalConfirmed": 499997,
                "failedCodes": ["27984470000000", "264795300", "2944650047"]
            },
            "logId": "234234"
        }
        """;

    private const string NoMatchBody =
        """
        {
            "message": "No valid unique codes found",
            "data": { "status": "failed", "totalConfirmed": 0 },
            "logId": "234234"
        }
        """;

    private static ConfirmUniqueCodeRequest SampleRequest() => new()
    {
        EventId = 1,
        VendorId = 3,
        Confirmations =
        {
            new Confirmation { BatchId = "1", Code = "ABC123", Date = new DateOnly(2025, 10, 29) },
        },
    };

    [Fact]
    public async Task Confirm_ParsesFullSuccess()
    {
        var handler = new StubHttpMessageHandler().EnqueueJson(HttpStatusCode.OK, FullSuccessBody);
        var client = TestFactory.CreateClient(handler);

        var response = await client.ConfirmUniqueCodesAsync(SampleRequest());

        Assert.Equal("All unique codes confirmed successfully", response.Message);
        Assert.Equal("234234", response.LogId);
        Assert.Equal(ConfirmationStatus.Success, response.Data!.Status);
        Assert.Equal(499997, response.Data.TotalConfirmed);
        Assert.Null(response.Data.FailedCodes);
    }

    [Fact]
    public async Task Confirm_ParsesPartialSuccessWithFailedCodes()
    {
        var handler = new StubHttpMessageHandler().EnqueueJson(HttpStatusCode.OK, PartialSuccessBody);
        var client = TestFactory.CreateClient(handler);

        var response = await client.ConfirmUniqueCodesAsync(SampleRequest());

        Assert.Equal(ConfirmationStatus.PartialSuccess, response.Data!.Status);
        Assert.Equal(499997, response.Data.TotalConfirmed);
        Assert.Equal(
            new[] { "27984470000000", "264795300", "2944650047" },
            response.Data.FailedCodes!.ToArray());
    }

    [Fact]
    public async Task Confirm_ThrowsWithStructuredDataOnNoMatch()
    {
        var handler = new StubHttpMessageHandler().EnqueueJson(HttpStatusCode.BadRequest, NoMatchBody);
        var client = TestFactory.CreateClient(handler);

        var ex = await Assert.ThrowsAsync<UniqueCodeApiException>(() =>
            client.ConfirmUniqueCodesAsync(SampleRequest()));

        Assert.Equal(HttpStatusCode.BadRequest, ex.StatusCode);
        Assert.Equal("No valid unique codes found", ex.ApiMessage);
        Assert.NotNull(ex.ConfirmData);
        Assert.Equal(ConfirmationStatus.Failed, ex.ConfirmData!.Status);
        Assert.Equal(0, ex.ConfirmData.TotalConfirmed);
    }

    [Fact]
    public async Task Confirm_SerializesDateAsIsoDate()
    {
        var handler = new StubHttpMessageHandler().EnqueueJson(HttpStatusCode.OK, FullSuccessBody);
        var client = TestFactory.CreateClient(handler);

        await client.ConfirmUniqueCodesAsync(SampleRequest());

        var recorded = Assert.Single(handler.Requests);
        Assert.Equal(
            "https://devloyaltyapi.wingscorp.com/v1/unique-code-prize/confirm-unique-code",
            recorded.Uri!.ToString());

        using var doc = JsonDocument.Parse(recorded.Body);
        var confirmation = doc.RootElement.GetProperty("confirmations")[0];
        Assert.Equal("1", confirmation.GetProperty("batchId").GetString());
        Assert.Equal("ABC123", confirmation.GetProperty("code").GetString());
        Assert.Equal("2025-10-29", confirmation.GetProperty("date").GetString());
    }

    [Fact]
    public async Task Confirm_RejectsOverLimitInSingleCall()
    {
        var handler = new StubHttpMessageHandler();
        var client = TestFactory.CreateClient(handler);

        var request = new ConfirmUniqueCodeRequest { EventId = 1, VendorId = 3 };
        for (var i = 0; i < UniqueCodeClientOptions.MaxConfirmCodesPerCall + 1; i++)
        {
            request.Confirmations.Add(new Confirmation
            {
                BatchId = "1",
                Code = $"CODE{i}",
                Date = new DateOnly(2025, 10, 29),
            });
        }

        var ex = await Assert.ThrowsAsync<ArgumentException>(() => client.ConfirmUniqueCodesAsync(request));
        Assert.Contains("200,000", ex.Message);
        Assert.Empty(handler.Requests);
    }

    [Fact]
    public async Task ConfirmBatched_SplitsInto200kChunks()
    {
        var handler = new StubHttpMessageHandler()
            .EnqueueJson(HttpStatusCode.OK, FullSuccessBody)
            .EnqueueJson(HttpStatusCode.OK, FullSuccessBody)
            .EnqueueJson(HttpStatusCode.OK, FullSuccessBody);
        var client = TestFactory.CreateClient(handler);

        var request = new ConfirmUniqueCodeRequest { EventId = 1, VendorId = 3 };
        for (var i = 0; i < 450_000; i++)
        {
            request.Confirmations.Add(new Confirmation
            {
                BatchId = "1",
                Code = $"CODE{i}",
                Date = new DateOnly(2025, 10, 29),
            });
        }

        var responses = await client.ConfirmUniqueCodesBatchedAsync(request);

        // 450k -> 200k + 200k + 50k = 3 calls.
        Assert.Equal(3, responses.Count);
        Assert.Equal(3, handler.Requests.Count);
    }
}
