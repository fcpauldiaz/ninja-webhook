using System.Text.Json.Serialization;

namespace WebhookReceiver.Models;

public sealed class TradeCommand
{
    [JsonPropertyName("id")]
    public string? Id { get; set; }

    [JsonPropertyName("timestamp")]
    public string? Timestamp { get; set; }

    [JsonPropertyName("secret")]
    public string? Secret { get; set; }

    [JsonPropertyName("source")]
    public string? Source { get; set; }

    [JsonPropertyName("symbol")]
    public string? Symbol { get; set; }

    [JsonPropertyName("ntSymbol")]
    public string? NtSymbol { get; set; }

    [JsonPropertyName("action")]
    public string? Action { get; set; }

    [JsonPropertyName("orderType")]
    public string? OrderType { get; set; }

    [JsonPropertyName("quantity")]
    public int? Quantity { get; set; }

    [JsonPropertyName("account")]
    public string? Account { get; set; }

    [JsonPropertyName("timeInForce")]
    public string? TimeInForce { get; set; }

    [JsonPropertyName("comment")]
    public string? Comment { get; set; }

    [JsonPropertyName("stopLossTicks")]
    public int? StopLossTicks { get; set; }

    [JsonPropertyName("profitTargetTicks")]
    public int? ProfitTargetTicks { get; set; }

    public TradeCommand CloneWithoutSecret()
    {
        return new TradeCommand
        {
            Id = Id,
            Timestamp = Timestamp,
            Source = Source,
            Symbol = Symbol,
            NtSymbol = NtSymbol,
            Action = Action,
            OrderType = OrderType,
            Quantity = Quantity,
            Account = Account,
            TimeInForce = TimeInForce,
            Comment = Comment,
            StopLossTicks = StopLossTicks,
            ProfitTargetTicks = ProfitTargetTicks
        };
    }
}
