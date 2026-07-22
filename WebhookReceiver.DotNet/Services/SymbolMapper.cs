using Microsoft.Extensions.Options;
using WebhookReceiver.Models;

namespace WebhookReceiver.Services;

public sealed class SymbolMapper
{
    private readonly Dictionary<string, string> _map;

    public SymbolMapper(IOptions<SymbolMapOptions> options)
    {
        _map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pair in options.Value.Entries)
            _map[pair.Key.Trim()] = pair.Value.Trim();
    }

    public bool TryResolve(TradeCommand command, out string? error)
    {
        error = null;

        if (!string.IsNullOrWhiteSpace(command.NtSymbol))
        {
            command.NtSymbol = command.NtSymbol.Trim();
            return true;
        }

        if (string.IsNullOrWhiteSpace(command.Symbol))
        {
            error = "Either symbol or ntSymbol is required.";
            return false;
        }

        var key = command.Symbol.Trim();
        if (_map.TryGetValue(key, out var mapped) && !string.IsNullOrWhiteSpace(mapped))
        {
            command.NtSymbol = mapped;
            return true;
        }

        error = $"No NinjaTrader symbol mapping found for '{key}'. Set ntSymbol or add SymbolMap entry.";
        return false;
    }
}
