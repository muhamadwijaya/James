using System.Net;
using System.Text.Json;
using Fukusuke.UniqueCode.Client;
using Fukusuke.UniqueCode.Client.Models;
using Xunit;

namespace Fukusuke.UniqueCode.Tests;

public class RequestUniqueCodeTests
{
    private const string SuccessBody =
        """
        {
          "message": "Success",
          "data": {
            "batchId": "1",
            "eventId": 1,
            "materials": [
              {
                "materialId": "12345",
                "materialName": "variant1",
                "prizeId": null,
                "prizeName": "",
                "requestedCodes": 2,
                "codes": ["ABC125", "ABC126"]
              }
            ],
            "sendDate": "2025-12-05T10:30:00+07:00"
          }
        }
        """;

    [Fact]
    public async Task RequestUniqueCodes_ParsesSuccessResponse()
    {
        var handler = new StubHttpMessageHandler().EnqueueJson(HttpStatusCode.OK, SuccessBody);
        var client = TestFactory.CreateClient(handler);

        var response = await client.RequestUniqueCodesAsync(new RequestUniqueCodeRequest
        {
            EventId = 1,
            VendorId = 1,
            Materials = { new MaterialRequest { MaterialId = "12345", PrizeId = null, Quantity = 2 } },
        });

        Assert.Equal("Success", response.Message);
        Assert.NotNull(response.Data);
        Assert.Equal("1", response.Data!.BatchId);
        var material = Assert.Single(response.Data.Materials);
        Assert.Equal("12345", material.MaterialId);
        Assert.Equal(2, material.RequestedCodes);
        Assert.Equal(new[] { "ABC125", "ABC126" }, material.Codes);
        Assert.Equal(
            new DateTimeOffset(2025, 12, 5, 10, 30, 0, TimeSpan.FromHours(7)),
            response.Data.SendDate);
    }

    [Fact]
    public async Task RequestUniqueCodes_SendsApiKeyAndCorrectEndpoint()
    {
        var handler = new StubHttpMessageHandler().EnqueueJson(HttpStatusCode.OK, SuccessBody);
        var client = TestFactory.CreateClient(handler);

        await client.RequestUniqueCodesAsync(new RequestUniqueCodeRequest
        {
            EventId = 13,
            VendorId = 6,
            Materials = { new MaterialRequest { MaterialId = "000001", Quantity = 2 } },
        });

        var recorded = Assert.Single(handler.Requests);
        Assert.Equal(HttpMethod.Post, recorded.Method);
        Assert.Equal(
            "https://devloyaltyapi.wingscorp.com/v1/unique-code-prize/request-unique-code",
            recorded.Uri!.ToString());
        Assert.Equal(TestFactory.ApiKey, recorded.ApiKey);
        Assert.Contains("application/json", recorded.Accept);

        using var doc = JsonDocument.Parse(recorded.Body);
        Assert.Equal(13, doc.RootElement.GetProperty("eventId").GetInt32());
        Assert.Equal(6, doc.RootElement.GetProperty("vendorId").GetInt32());
        var material = doc.RootElement.GetProperty("materials")[0];
        Assert.Equal("000001", material.GetProperty("materialId").GetString());
        Assert.Equal(JsonValueKind.Null, material.GetProperty("prizeId").ValueKind);
        Assert.Equal(2, material.GetProperty("quantity").GetInt32());
    }

    [Theory]
    [InlineData(HttpStatusCode.BadRequest, "{\"message\":\"Event not found\",\"data\":null}", "Event not found")]
    [InlineData(HttpStatusCode.BadRequest, "{\"message\":\"Vendor not found\",\"data\":null}", "Vendor not found")]
    [InlineData(HttpStatusCode.BadRequest, "{\"message\":\"Unique code habis untuk material 000003\",\"data\":null}", "Unique code habis untuk material 000003")]
    [InlineData(HttpStatusCode.InternalServerError, "{\"message\":\"Internal server error\",\"data\":null}", "Internal server error")]
    public async Task RequestUniqueCodes_ThrowsOnDocumentedErrors(
        HttpStatusCode statusCode, string body, string expectedMessage)
    {
        var handler = new StubHttpMessageHandler().EnqueueJson(statusCode, body);
        var client = TestFactory.CreateClient(handler);

        var ex = await Assert.ThrowsAsync<UniqueCodeApiException>(() =>
            client.RequestUniqueCodesAsync(new RequestUniqueCodeRequest
            {
                EventId = 1,
                VendorId = 1,
                Materials = { new MaterialRequest { MaterialId = "000003", Quantity = 2 } },
            }));

        Assert.Equal(statusCode, ex.StatusCode);
        Assert.Equal(expectedMessage, ex.ApiMessage);
    }

    [Fact]
    public async Task RequestUniqueCodes_RejectsEmptyMaterials()
    {
        var handler = new StubHttpMessageHandler();
        var client = TestFactory.CreateClient(handler);

        await Assert.ThrowsAsync<ArgumentException>(() =>
            client.RequestUniqueCodesAsync(new RequestUniqueCodeRequest { EventId = 1, VendorId = 1 }));
    }

    [Fact]
    public async Task RequestUniqueCodes_RejectsOverLimitInSingleCall()
    {
        var handler = new StubHttpMessageHandler();
        var client = TestFactory.CreateClient(handler);

        var ex = await Assert.ThrowsAsync<ArgumentException>(() =>
            client.RequestUniqueCodesAsync(new RequestUniqueCodeRequest
            {
                EventId = 1,
                VendorId = 1,
                Materials = { new MaterialRequest { MaterialId = "000001", Quantity = 500_001 } },
            }));

        Assert.Contains("500,000", ex.Message);
        Assert.Empty(handler.Requests);
    }

    [Fact]
    public async Task RequestUniqueCodesBatched_SplitsAcrossCalls()
    {
        var handler = new StubHttpMessageHandler()
            .EnqueueJson(HttpStatusCode.OK, SuccessBody)
            .EnqueueJson(HttpStatusCode.OK, SuccessBody);
        var client = TestFactory.CreateClient(handler);

        var responses = await client.RequestUniqueCodesBatchedAsync(new RequestUniqueCodeRequest
        {
            EventId = 13,
            VendorId = 6,
            Materials =
            {
                new MaterialRequest { MaterialId = "000001", Quantity = 300_000 },
                new MaterialRequest { MaterialId = "000002", Quantity = 300_000 },
            },
        });

        // 300k + 300k = 600k -> must be split into two calls of <= 500k each.
        Assert.Equal(2, responses.Count);
        Assert.Equal(2, handler.Requests.Count);
    }
}
