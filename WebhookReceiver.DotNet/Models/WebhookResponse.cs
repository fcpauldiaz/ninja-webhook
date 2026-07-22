using System.Text.Json.Serialization;

namespace WebhookReceiver.Models;

public sealed class WebhookResponse
{
    [JsonPropertyName("status")]
    public required string Status { get; init; }

    [JsonPropertyName("id")]
    public string? Id { get; init; }

    [JsonPropertyName("ntSymbol")]
    public string? NtSymbol { get; init; }

    [JsonPropertyName("reason")]
    public string? Reason { get; init; }

    public static WebhookResponse Accepted(string id, string? ntSymbol) =>
        new() { Status = "accepted", Id = id, NtSymbol = ntSymbol };

    public static WebhookResponse DryRun(string id, string? ntSymbol) =>
        new() { Status = "dry_run", Id = id, NtSymbol = ntSymbol };

    public static WebhookResponse Rejected(string? id, string reason) =>
        new() { Status = "rejected", Id = id, Reason = reason };
}
