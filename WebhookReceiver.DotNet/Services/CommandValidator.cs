using Microsoft.Extensions.Options;
using WebhookReceiver.Models;

namespace WebhookReceiver.Services;

public sealed class CommandValidator
{
    private readonly RiskOptions _risk;
    private readonly TradingHoursGuard _tradingHours;
    private readonly SymbolMapper _symbolMapper;

    public CommandValidator(
        IOptions<RiskOptions> risk,
        TradingHoursGuard tradingHours,
        SymbolMapper symbolMapper)
    {
        _risk = risk.Value;
        _tradingHours = tradingHours;
        _symbolMapper = symbolMapper;
    }

    public bool TryValidateAndNormalize(TradeCommand command, out string? error)
    {
        error = null;

        if (!_risk.EnableTrading)
        {
            error = "Trading is disabled by Risk:EnableTrading=false.";
            return false;
        }

        if (!_tradingHours.IsWithinTradingHours(out var hoursReason))
        {
            error = hoursReason;
            return false;
        }

        command.Action = NormalizeToken(command.Action);
        command.OrderType = NormalizeToken(command.OrderType) ?? "MARKET";
        command.TimeInForce = NormalizeToken(command.TimeInForce) ?? "DAY";
        command.Source = string.IsNullOrWhiteSpace(command.Source) ? "Unknown" : command.Source.Trim();
        command.Symbol = string.IsNullOrWhiteSpace(command.Symbol) ? null : command.Symbol.Trim();
        // Account is chosen in the NinjaTrader listener panel — ignore payload account.
        command.Account = null;

        if (string.IsNullOrWhiteSpace(command.Id))
            command.Id = Guid.NewGuid().ToString("N");
        else
            command.Id = command.Id.Trim();

        if (string.IsNullOrWhiteSpace(command.Timestamp))
            command.Timestamp = DateTime.UtcNow.ToString("o");

        if (string.IsNullOrWhiteSpace(command.Action))
        {
            error = "action is required.";
            return false;
        }

        if (!_risk.AllowedActions.Any(a => string.Equals(a, command.Action, StringComparison.OrdinalIgnoreCase)))
        {
            error = $"action '{command.Action}' is not allowed.";
            return false;
        }

        if (!_risk.AllowedOrderTypes.Any(t => string.Equals(t, command.OrderType, StringComparison.OrdinalIgnoreCase)))
        {
            error = $"orderType '{command.OrderType}' is not allowed.";
            return false;
        }

        if (!string.Equals(command.OrderType, "MARKET", StringComparison.OrdinalIgnoreCase))
        {
            error = "Only MARKET orders are supported in this version.";
            return false;
        }

        if (command.Quantity is null || command.Quantity <= 0)
        {
            error = "quantity must be a positive integer.";
            return false;
        }

        if (command.Quantity > _risk.MaxQuantity)
        {
            error = $"quantity {command.Quantity} exceeds MaxQuantity {_risk.MaxQuantity}.";
            return false;
        }

        if (!_symbolMapper.TryResolve(command, out var mapError))
        {
            error = mapError;
            return false;
        }

        if (_risk.AllowedSymbols.Count > 0)
        {
            var symbolOk = _risk.AllowedSymbols.Any(s =>
                string.Equals(s, command.Symbol, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(s, command.NtSymbol, StringComparison.OrdinalIgnoreCase));

            if (!symbolOk)
            {
                error = $"symbol '{command.Symbol}' / ntSymbol '{command.NtSymbol}' is not in AllowedSymbols.";
                return false;
            }
        }

        return true;
    }

    private static string? NormalizeToken(string? value) =>
        string.IsNullOrWhiteSpace(value) ? null : value.Trim().ToUpperInvariant();
}
