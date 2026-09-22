using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Fukusuke.UniqueCode.Client.Json;

/// <summary>
/// Serializes <see cref="DateOnly"/> values using the ISO <c>yyyy-MM-dd</c> format,
/// matching the <c>date</c> field of the confirm-unique-code request body.
/// </summary>
public sealed class DateOnlyJsonConverter : JsonConverter<DateOnly>
{
    private const string Format = "yyyy-MM-dd";

    public override DateOnly Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        var value = reader.GetString();
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new JsonException("Expected a non-empty date string in yyyy-MM-dd format.");
        }

        return DateOnly.ParseExact(value, Format, CultureInfo.InvariantCulture);
    }

    public override void Write(Utf8JsonWriter writer, DateOnly value, JsonSerializerOptions options)
    {
        writer.WriteStringValue(value.ToString(Format, CultureInfo.InvariantCulture));
    }
}
