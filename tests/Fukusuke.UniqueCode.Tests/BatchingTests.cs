using Fukusuke.UniqueCode.Client;
using Fukusuke.UniqueCode.Client.Models;
using Xunit;

namespace Fukusuke.UniqueCode.Tests;

public class BatchingTests
{
    [Fact]
    public void BatchMaterials_KeepsBatchesUnderLimit()
    {
        var materials = new List<MaterialRequest>
        {
            new() { MaterialId = "A", Quantity = 200_000 },
            new() { MaterialId = "B", Quantity = 200_000 },
            new() { MaterialId = "C", Quantity = 200_000 },
        };

        var batches = UniqueCodeClient
            .BatchMaterials(materials, UniqueCodeClientOptions.MaxRequestCodesPerCall)
            .ToList();

        // 200k * 3 = 600k -> [A+B = 400k][C = 200k]
        Assert.Equal(2, batches.Count);
        Assert.All(batches, b => Assert.True(b.Sum(m => (long)m.Quantity) <= UniqueCodeClientOptions.MaxRequestCodesPerCall));
        Assert.Equal(3, batches.Sum(b => b.Count));
    }

    [Fact]
    public void BatchMaterials_SingleMaterialExactlyAtLimit_IsOneBatch()
    {
        var materials = new List<MaterialRequest>
        {
            new() { MaterialId = "A", Quantity = UniqueCodeClientOptions.MaxRequestCodesPerCall },
        };

        var batches = UniqueCodeClient
            .BatchMaterials(materials, UniqueCodeClientOptions.MaxRequestCodesPerCall)
            .ToList();

        Assert.Single(batches);
    }

    [Fact]
    public void BatchMaterials_MaterialOverLimit_Throws()
    {
        var materials = new List<MaterialRequest>
        {
            new() { MaterialId = "A", Quantity = UniqueCodeClientOptions.MaxRequestCodesPerCall + 1 },
        };

        Assert.Throws<ArgumentException>(() =>
            UniqueCodeClient.BatchMaterials(materials, UniqueCodeClientOptions.MaxRequestCodesPerCall).ToList());
    }
}
