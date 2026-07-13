using System.Globalization;

namespace GovTech.Api.Modules;

public record FireHotspot(double Lat, double Lon, double Frp, string Date, string Time, string Satellite);

/// <summary>
/// Прокси к NASA FIRMS (активные очаги за последние 24 ч по Казахстану).
/// Ключ — бесплатный MAP_KEY (firms.modaps.eosdis.nasa.gov/api), задаётся через
/// FIRMS_MAP_KEY в .env. Кэш 15 минут — чаще FIRMS не обновляется и просит не долбить API.
/// </summary>
public static class FireEndpoints
{
    private const string KazakhstanBbox = "46,40,88,56"; // west,south,east,north
    // SNPP выведен из NRT (2026) — рабочие сенсоры VIIRS: NOAA-20 и NOAA-21
    private static readonly string[] Sensors = ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"];
    private static readonly TimeSpan CacheTtl = TimeSpan.FromMinutes(15);
    private static readonly SemaphoreSlim FetchLock = new(1, 1);
    private static (DateTimeOffset At, List<FireHotspot> Data)? _cache;

    public static void MapFireEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/fire").WithTags("Fire").RequireAuthorization();

        group.MapGet("/hotspots", async (IConfiguration configuration, IHttpClientFactory httpClientFactory) =>
        {
            var key = configuration["Firms:MapKey"];
            if (string.IsNullOrWhiteSpace(key))
                return Results.Json(
                    new { error = "FIRMS_MAP_KEY не задан в .env — бесплатный ключ: firms.modaps.eosdis.nasa.gov/api" },
                    statusCode: StatusCodes.Status503ServiceUnavailable);

            if (_cache is { } cached && DateTimeOffset.UtcNow - cached.At < CacheTtl)
                return Results.Ok(cached.Data);

            await FetchLock.WaitAsync();
            try
            {
                if (_cache is { } fresh && DateTimeOffset.UtcNow - fresh.At < CacheTtl)
                    return Results.Ok(fresh.Data);

                var client = httpClientFactory.CreateClient("firms");
                var hotspots = new List<FireHotspot>();
                foreach (var sensor in Sensors)
                {
                    var url = $"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/{KazakhstanBbox}/1";
                    var csv = await client.GetStringAsync(url);
                    if (!csv.StartsWith("latitude"))
                        return Results.Json(new { error = $"FIRMS ({sensor}): {csv[..Math.Min(csv.Length, 200)].Trim()}" },
                            statusCode: StatusCodes.Status502BadGateway);
                    hotspots.AddRange(ParseFirmsCsv(csv));
                }
                _cache = (DateTimeOffset.UtcNow, hotspots);
                return Results.Ok(hotspots);
            }
            catch (HttpRequestException ex)
            {
                return Results.Json(new { error = $"FIRMS недоступен: {ex.Message}" },
                    statusCode: StatusCodes.Status502BadGateway);
            }
            finally
            {
                FetchLock.Release();
            }
        });
    }

    private static List<FireHotspot> ParseFirmsCsv(string csv)
    {
        var lines = csv.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (lines.Length < 2) return [];

        var header = lines[0].Split(',');
        int Col(string name) => Array.IndexOf(header, name);
        int latCol = Col("latitude"), lonCol = Col("longitude"), frpCol = Col("frp"),
            dateCol = Col("acq_date"), timeCol = Col("acq_time"), satCol = Col("satellite");
        if (latCol < 0 || lonCol < 0) return [];

        var result = new List<FireHotspot>();
        foreach (var line in lines.Skip(1))
        {
            var parts = line.Split(',');
            if (parts.Length <= Math.Max(frpCol, timeCol)) continue;
            if (!double.TryParse(parts[latCol], CultureInfo.InvariantCulture, out var lat)) continue;
            if (!double.TryParse(parts[lonCol], CultureInfo.InvariantCulture, out var lon)) continue;
            double.TryParse(parts[frpCol], CultureInfo.InvariantCulture, out var frp);
            result.Add(new FireHotspot(lat, lon, frp,
                dateCol >= 0 ? parts[dateCol] : "", timeCol >= 0 ? parts[timeCol] : "",
                satCol >= 0 ? parts[satCol] : ""));
        }
        return result;
    }
}
