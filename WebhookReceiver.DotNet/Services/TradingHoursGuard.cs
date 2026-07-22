using Microsoft.Extensions.Options;
using WebhookReceiver.Models;

namespace WebhookReceiver.Services;

public sealed class TradingHoursGuard
{
    private readonly TradingHoursOptions _options;
    private readonly TimeZoneInfo _timeZone;
    private readonly TimeOnly _start;
    private readonly TimeOnly _end;

    public TradingHoursGuard(IOptions<TradingHoursOptions> options)
    {
        _options = options.Value;
        _timeZone = ResolveTimeZone(_options.TimeZone);
        _start = TimeOnly.Parse(_options.Start);
        _end = TimeOnly.Parse(_options.End);
    }

    public bool IsWithinTradingHours(out string? reason)
    {
        reason = null;
        if (!_options.Enabled)
            return true;

        var localNow = TimeOnly.FromDateTime(TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _timeZone));
        var open = _start <= _end
            ? localNow >= _start && localNow <= _end
            : localNow >= _start || localNow <= _end;

        if (open)
            return true;

        reason = $"Outside trading hours ({_options.Start}-{_options.End} {_options.TimeZone}).";
        return false;
    }

    private static TimeZoneInfo ResolveTimeZone(string id)
    {
        try
        {
            return TimeZoneInfo.FindSystemTimeZoneById(id);
        }
        catch (TimeZoneNotFoundException)
        {
            // Linux/macOS often use IANA; Windows may need the Windows id.
            if (string.Equals(id, "America/New_York", StringComparison.OrdinalIgnoreCase))
                return TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");

            throw;
        }
    }
}
