using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Options;
using WebhookReceiver.Models;
using WebhookReceiver.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<WebhookOptions>(builder.Configuration.GetSection(WebhookOptions.SectionName));
builder.Services.Configure<RiskOptions>(builder.Configuration.GetSection(RiskOptions.SectionName));
builder.Services.Configure<TcpOptions>(builder.Configuration.GetSection(TcpOptions.SectionName));
builder.Services.Configure<DedupeOptions>(builder.Configuration.GetSection(DedupeOptions.SectionName));
builder.Services.Configure<TradingHoursOptions>(builder.Configuration.GetSection(TradingHoursOptions.SectionName));
builder.Services.Configure<SymbolMapOptions>(options =>
{
    var section = builder.Configuration.GetSection(SymbolMapOptions.SectionName);
    options.Entries = section.GetChildren()
        .Where(c => !string.IsNullOrWhiteSpace(c.Value))
        .ToDictionary(c => c.Key, c => c.Value!, StringComparer.OrdinalIgnoreCase);
});

builder.Services.AddSingleton<SymbolMapper>();
builder.Services.AddSingleton<DuplicateCommandCache>();
builder.Services.AddSingleton<TradingHoursGuard>();
builder.Services.AddSingleton<CommandValidator>();
builder.Services.AddSingleton<TcpForwarder>();

builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    options.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
});

var app = builder.Build();
var logger = app.Logger;

app.MapGet("/health", () => Results.Ok(new
{
    status = "ok",
    utc = DateTime.UtcNow.ToString("o")
}));

app.MapPost("/webhook", async (
    HttpRequest request,
    TradeCommand? command,
    CommandValidator validator,
    DuplicateCommandCache dedupe,
    TcpForwarder forwarder,
    IOptions<WebhookOptions> webhookOptions,
    ILoggerFactory loggerFactory,
    CancellationToken cancellationToken) =>
{
    var log = loggerFactory.CreateLogger("Webhook");
    var options = webhookOptions.Value;

    if (command is null)
    {
        log.LogWarning("Rejected: empty or invalid JSON body");
        return Results.BadRequest(WebhookResponse.Rejected(null, "Invalid or empty JSON body."));
    }

    log.LogInformation(
        "Received command candidate id={Id} source={Source} symbol={Symbol} action={Action} qty={Qty}",
        command.Id,
        command.Source,
        command.Symbol,
        command.Action,
        command.Quantity);

    var headerSecret = request.Headers["X-Webhook-Secret"].FirstOrDefault();
    var providedSecret = !string.IsNullOrWhiteSpace(headerSecret) ? headerSecret : command.Secret;

    if (string.IsNullOrWhiteSpace(options.Secret) ||
        string.IsNullOrWhiteSpace(providedSecret) ||
        !FixedTimeEquals(options.Secret, providedSecret))
    {
        log.LogWarning("Rejected command {CommandId}: invalid webhook secret", command.Id);
        return Results.Json(
            WebhookResponse.Rejected(command.Id, "Invalid webhook secret."),
            statusCode: StatusCodes.Status401Unauthorized);
    }

    // Prefer header secret; never forward body secret to NinjaTrader.
    command.Secret = null;

    if (!validator.TryValidateAndNormalize(command, out var validationError))
    {
        log.LogWarning("Rejected command {CommandId}: {Reason}", command.Id, validationError);
        return Results.BadRequest(WebhookResponse.Rejected(command.Id, validationError!));
    }

    log.LogInformation(
        "Validated command {CommandId} ntSymbol={NtSymbol} account={Account}",
        command.Id,
        command.NtSymbol,
        command.Account);

    if (!dedupe.TryAccept(command.Id!))
    {
        log.LogWarning("Rejected duplicate command {CommandId}", command.Id);
        return Results.Json(
            WebhookResponse.Rejected(command.Id, "Duplicate command id within dedupe window."),
            statusCode: StatusCodes.Status409Conflict);
    }

    if (options.DryRun)
    {
        log.LogInformation("DryRun enabled — not forwarding command {CommandId}", command.Id);
        return Results.Ok(WebhookResponse.DryRun(command.Id!, command.NtSymbol));
    }

    try
    {
        await forwarder.ForwardAsync(command, cancellationToken);
        log.LogInformation("Accepted and forwarded command {CommandId}", command.Id);
        return Results.Ok(WebhookResponse.Accepted(command.Id!, command.NtSymbol));
    }
    catch (Exception ex)
    {
        log.LogError(ex, "Failed to forward command {CommandId} to NinjaTrader TCP listener", command.Id);
        return Results.Json(
            WebhookResponse.Rejected(command.Id, $"Failed to reach NinjaTrader TCP listener: {ex.Message}"),
            statusCode: StatusCodes.Status502BadGateway);
    }
});

logger.LogInformation(
    "WebhookReceiver started. POST /webhook  GET /health  DryRun={DryRun}",
    app.Configuration.GetValue<bool>("Webhook:DryRun"));

app.Run();

static bool FixedTimeEquals(string expected, string provided)
{
    var a = System.Text.Encoding.UTF8.GetBytes(expected);
    var b = System.Text.Encoding.UTF8.GetBytes(provided);
    if (a.Length != b.Length)
        return false;

    return System.Security.Cryptography.CryptographicOperations.FixedTimeEquals(a, b);
}
