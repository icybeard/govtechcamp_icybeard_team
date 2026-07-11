using GovTech.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Modules;

public record RegionDto(int Id, string IsoCode, string NameEn, string NameRu);
public record UpsertMetricsRequest(string Module, string MetricKey, string? Period, Dictionary<string, double> Values);

public static class RegionEndpoints
{
    public static void MapRegionEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/regions").WithTags("Regions").RequireAuthorization();

        group.MapGet("/", async (AppDbContext db) =>
            await db.Regions.OrderBy(r => r.NameRu)
                .Select(r => new RegionDto(r.Id, r.IsoCode, r.NameEn, r.NameRu))
                .ToListAsync());

        // Значения метрики для заливки карты: { "KZ-PAV": 45.0, ... }
        group.MapGet("/metrics/{module}", async (string module, string? metricKey, string? period, AppDbContext db) =>
        {
            var query = db.RegionMetrics.Where(m => m.Module == module);
            if (!string.IsNullOrEmpty(metricKey)) query = query.Where(m => m.MetricKey == metricKey);
            if (!string.IsNullOrEmpty(period)) query = query.Where(m => m.Period == period);

            var values = await query
                .Join(db.Regions, m => m.RegionId, r => r.Id, (m, r) => new { r.IsoCode, m.Value })
                .ToDictionaryAsync(x => x.IsoCode, x => x.Value);

            return Results.Ok(values);
        });

        // Загрузка метрик из ML-пайплайна (только Admin): апсерт по (регион, module, metricKey, period).
        group.MapPut("/metrics", async (UpsertMetricsRequest request, AppDbContext db) =>
        {
            if (string.IsNullOrWhiteSpace(request.Module) || string.IsNullOrWhiteSpace(request.MetricKey))
                return Results.BadRequest(new { error = "Module и MetricKey обязательны" });

            var period = request.Period ?? "";
            var regions = await db.Regions.ToDictionaryAsync(r => r.IsoCode);
            var unknown = request.Values.Keys.Where(k => !regions.ContainsKey(k)).ToList();
            if (unknown.Count > 0)
                return Results.BadRequest(new { error = $"Неизвестные коды регионов: {string.Join(", ", unknown)}" });

            var existing = await db.RegionMetrics
                .Where(m => m.Module == request.Module && m.MetricKey == request.MetricKey && m.Period == period)
                .ToDictionaryAsync(m => m.RegionId);

            foreach (var (iso, value) in request.Values)
            {
                var regionId = regions[iso].Id;
                if (existing.TryGetValue(regionId, out var metric))
                {
                    metric.Value = value;
                    metric.UpdatedAt = DateTimeOffset.UtcNow;
                }
                else
                {
                    db.RegionMetrics.Add(new RegionMetric
                    {
                        RegionId = regionId,
                        Module = request.Module,
                        MetricKey = request.MetricKey,
                        Period = period,
                        Value = value
                    });
                }
            }

            await db.SaveChangesAsync();
            return Results.Ok(new { updated = request.Values.Count });
        }).RequireAuthorization(policy => policy.RequireRole(Roles.Admin));
    }
}
