namespace WebhookReceiver.Models;

public sealed class WebhookOptions
{
    public const string SectionName = "Webhook";

    public string Secret { get; set; } = "change-me-now";
    public bool DryRun { get; set; } = true;
}

public sealed class RiskOptions
{
    public const string SectionName = "Risk";

    public bool EnableTrading { get; set; }
    public int MaxQuantity { get; set; } = 1;
    public string DefaultAccount { get; set; } = "Sim101";
    public List<string> AllowedSymbols { get; set; } = new();
    public List<string> AllowedActions { get; set; } =
        new() { "BUY", "SELL", "EXIT_LONG", "EXIT_SHORT", "FLATTEN" };
    public List<string> AllowedOrderTypes { get; set; } = new() { "MARKET" };
    public List<string> AllowedAccounts { get; set; } = new() { "Sim101" };
}

public sealed class TcpOptions
{
    public const string SectionName = "Tcp";

    public string Host { get; set; } = "127.0.0.1";
    public int Port { get; set; } = 7077;
    public int ConnectTimeoutMs { get; set; } = 3000;
}

public sealed class DedupeOptions
{
    public const string SectionName = "Dedupe";

    public int WindowSeconds { get; set; } = 300;
}

public sealed class TradingHoursOptions
{
    public const string SectionName = "TradingHours";

    public bool Enabled { get; set; }
    public string TimeZone { get; set; } = "America/New_York";
    public string Start { get; set; } = "09:30";
    public string End { get; set; } = "16:00";
}

public sealed class SymbolMapOptions
{
    public const string SectionName = "SymbolMap";

    public Dictionary<string, string> Entries { get; set; } = new(StringComparer.OrdinalIgnoreCase);
}
