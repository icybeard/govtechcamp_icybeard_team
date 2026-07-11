using System.Text.Json;
using GovTech.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Modules;

public record SettlementDto(int Id, string Name, string? KatoCode, double Lat, double Lon, int? Population);

public record SettlementImportItem(string Name, double Lat, double Lon, int? Population, string? KatoCode);
public record SettlementImportRequest(string RegionIso, List<SettlementImportItem> Settlements);

public record SettlementMetricValue(double Value, List<MetricFactor>? Factors);
public record MetricFactor(string Name, double Impact);
public record UpsertSettlementMetricsRequest(string Module, string MetricKey, string? Period, Dictionary<int, SettlementMetricValue> Values);

public record SettlementScoreDto(int SettlementId, string Name, double Lat, double Lon, int? Population, double Value, List<MetricFactor>? Factors);

public static class SettlementEndpoints
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public static void MapSettlementEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/settlements").WithTags("Settlements").RequireAuthorization();

        // Список НП региона (для ML-пайплайна и фронтенда)
        group.MapGet("/", async (string? region, AppDbContext db) =>
        {
            var query = db.Settlements.AsQueryable();
            if (!string.IsNullOrEmpty(region))
                query = query.Where(s => s.Region!.IsoCode == region);

            return Results.Ok(await query
                .OrderBy(s => s.Name)
                .Select(s => new SettlementDto(s.Id, s.Name, s.KatoCode, s.Lat, s.Lon, s.Population))
                .ToListAsync());
        });

        // Скоры НП со факторами — для карты и панели «Почему»
        group.MapGet("/metrics/{module}", async (string module, string? metricKey, string? period, string? region, AppDbContext db) =>
        {
            var query = db.SettlementMetrics.Where(m => m.Module == module);
            if (!string.IsNullOrEmpty(metricKey)) query = query.Where(m => m.MetricKey == metricKey);
            if (!string.IsNullOrEmpty(period)) query = query.Where(m => m.Period == period);
            if (!string.IsNullOrEmpty(region)) query = query.Where(m => m.Settlement!.Region!.IsoCode == region);

            var rows = await query
                .Join(db.Settlements, m => m.SettlementId, s => s.Id,
                    (m, s) => new { s.Id, s.Name, s.Lat, s.Lon, s.Population, m.Value, m.FactorsJson })
                .ToListAsync();

            return Results.Ok(rows.Select(r => new SettlementScoreDto(
                r.Id, r.Name, r.Lat, r.Lon, r.Population, r.Value,
                r.FactorsJson is null ? null : JsonSerializer.Deserialize<List<MetricFactor>>(r.FactorsJson, JsonOptions))));
        });

        // Массовый импорт НП (скрипт B: OSM/КАТО → API). Upsert по (регион, имя).
        group.MapPost("/import", async (SettlementImportRequest request, AppDbContext db) =>
        {
            var region = await db.Regions.FirstOrDefaultAsync(r => r.IsoCode == request.RegionIso);
            if (region is null)
                return Results.BadRequest(new { error = $"Неизвестный регион: {request.RegionIso}" });
            if (request.Settlements.Count == 0)
                return Results.BadRequest(new { error = "Пустой список НП" });

            var existing = await db.Settlements
                .Where(s => s.RegionId == region.Id)
                .ToDictionaryAsync(s => s.Name);

            var created = 0;
            var updated = 0;
            foreach (var item in request.Settlements)
            {
                if (string.IsNullOrWhiteSpace(item.Name)) continue;
                var name = item.Name.Trim();
                if (existing.TryGetValue(name, out var settlement))
                {
                    settlement.Lat = item.Lat;
                    settlement.Lon = item.Lon;
                    settlement.Population = item.Population ?? settlement.Population;
                    settlement.KatoCode = item.KatoCode ?? settlement.KatoCode;
                    updated++;
                }
                else
                {
                    var fresh = new Settlement
                    {
                        RegionId = region.Id,
                        Name = name,
                        Lat = item.Lat,
                        Lon = item.Lon,
                        Population = item.Population,
                        KatoCode = item.KatoCode
                    };
                    db.Settlements.Add(fresh);
                    existing[name] = fresh;
                    created++;
                }
            }

            await db.SaveChangesAsync();
            return Results.Ok(new { created, updated });
        }).RequireAuthorization(policy => policy.RequireRole(Roles.Admin));

        // Загрузка скоров из ML-пайплайна (upsert по НП+module+metricKey+period)
        group.MapPut("/metrics", async (UpsertSettlementMetricsRequest request, AppDbContext db) =>
        {
            if (string.IsNullOrWhiteSpace(request.Module) || string.IsNullOrWhiteSpace(request.MetricKey))
                return Results.BadRequest(new { error = "Module и MetricKey обязательны" });

            var period = request.Period ?? "";
            var ids = request.Values.Keys.ToList();
            var known = await db.Settlements.Where(s => ids.Contains(s.Id)).Select(s => s.Id).ToListAsync();
            var unknown = ids.Except(known).ToList();
            if (unknown.Count > 0)
                return Results.BadRequest(new { error = $"Неизвестные id НП: {string.Join(", ", unknown.Take(10))}" });

            var existing = await db.SettlementMetrics
                .Where(m => m.Module == request.Module && m.MetricKey == request.MetricKey && m.Period == period)
                .ToDictionaryAsync(m => m.SettlementId);

            foreach (var (settlementId, payload) in request.Values)
            {
                var factorsJson = payload.Factors is null ? null : JsonSerializer.Serialize(payload.Factors, JsonOptions);
                if (existing.TryGetValue(settlementId, out var metric))
                {
                    metric.Value = payload.Value;
                    metric.FactorsJson = factorsJson;
                    metric.UpdatedAt = DateTimeOffset.UtcNow;
                }
                else
                {
                    db.SettlementMetrics.Add(new SettlementMetric
                    {
                        SettlementId = settlementId,
                        Module = request.Module,
                        MetricKey = request.MetricKey,
                        Period = period,
                        Value = payload.Value,
                        FactorsJson = factorsJson
                    });
                }
            }

            await db.SaveChangesAsync();
            return Results.Ok(new { updated = request.Values.Count });
        }).RequireAuthorization(policy => policy.RequireRole(Roles.Admin));
    }
}
