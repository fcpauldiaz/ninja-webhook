using System.Collections.Concurrent;
using Microsoft.Extensions.Options;
using WebhookReceiver.Models;

namespace WebhookReceiver.Services;

public sealed class DuplicateCommandCache
{
    private readonly ConcurrentDictionary<string, DateTimeOffset> _seen = new(StringComparer.Ordinal);
    private readonly TimeSpan _window;
    private readonly object _pruneLock = new();
    private DateTimeOffset _lastPrune = DateTimeOffset.MinValue;

    public DuplicateCommandCache(IOptions<DedupeOptions> options)
    {
        var seconds = Math.Max(1, options.Value.WindowSeconds);
        _window = TimeSpan.FromSeconds(seconds);
    }

    public bool TryAccept(string commandId)
    {
        PruneIfNeeded();

        var now = DateTimeOffset.UtcNow;
        if (_seen.TryGetValue(commandId, out var previous) && now - previous < _window)
            return false;

        _seen[commandId] = now;
        return true;
    }

    private void PruneIfNeeded()
    {
        var now = DateTimeOffset.UtcNow;
        if (now - _lastPrune < TimeSpan.FromSeconds(30))
            return;

        lock (_pruneLock)
        {
            if (now - _lastPrune < TimeSpan.FromSeconds(30))
                return;

            foreach (var pair in _seen)
            {
                if (now - pair.Value >= _window)
                    _seen.TryRemove(pair.Key, out _);
            }

            _lastPrune = now;
        }
    }
}
