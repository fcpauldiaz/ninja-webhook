using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Options;
using WebhookReceiver.Models;

namespace WebhookReceiver.Services;

public sealed class TcpForwarder
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    private readonly TcpOptions _options;
    private readonly ILogger<TcpForwarder> _logger;

    public TcpForwarder(IOptions<TcpOptions> options, ILogger<TcpForwarder> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    public async Task ForwardAsync(TradeCommand command, CancellationToken cancellationToken)
    {
        var payload = command.CloneWithoutSecret();
        var line = JsonSerializer.Serialize(payload, JsonOptions) + "\n";
        var bytes = Encoding.UTF8.GetBytes(line);

        using var client = new TcpClient();
        using var connectCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        connectCts.CancelAfter(_options.ConnectTimeoutMs);

        _logger.LogInformation(
            "Forwarding command {CommandId} to {Host}:{Port}",
            payload.Id,
            _options.Host,
            _options.Port);

        await client.ConnectAsync(_options.Host, _options.Port, connectCts.Token);
        await using var stream = client.GetStream();
        await stream.WriteAsync(bytes, connectCts.Token);
        await stream.FlushAsync(connectCts.Token);

        _logger.LogInformation("Forwarded command {CommandId} successfully", payload.Id);
    }
}
