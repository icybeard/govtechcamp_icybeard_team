using System.Security.Claims;
using GovTech.Api.Auth;
using GovTech.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Modules;

public record MeasureDto(long Id, int SettlementId, string SettlementName, string Module, string Title,
    string? Description, string Status, double Priority, string? DecidedByName, DateTimeOffset? DecidedAt, string? Note);

public record CreateMeasureRequest(int SettlementId, string Module, string Title, string? Description);
public record GenerateMeasuresRequest(string Module, string MetricKey, string? Period);
public record ChangeMeasureStatusRequest(string Status, string? Note);

public static class MeasureEndpoints
{
    // Правила генерации черновиков для модуля паводков: порог скора → мера.
    private static readonly (double MinScore, string Title)[] FloodRules =
    [
        (70, "Обследование дамб и водопропускных сооружений"),
        (70, "Актуализация плана эвакуации"),
        (40, "Очистка русла и водопропускных труб"),
        (20, "Усиленный мониторинг снегозапаса и уровня воды")
    ];

    public static void MapMeasureEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/measures").WithTags("Measures").RequireAuthorization();

        static MeasureDto ToDto(PreventiveMeasure m) => new(
            m.Id, m.SettlementId, m.Settlement?.Name ?? "", m.Module, m.Title,
            m.Description, m.Status, m.Priority, m.DecidedByName, m.DecidedAt, m.Note);

        // Очередь мер: по умолчанию по убыванию приоритета
        group.MapGet("/", async (string? module, string? status, int? settlementId, AppDbContext db) =>
        {
            var query = db.PreventiveMeasures.Include(m => m.Settlement).AsQueryable();
            if (!string.IsNullOrEmpty(module)) query = query.Where(m => m.Module == module);
            if (!string.IsNullOrEmpty(status)) query = query.Where(m => m.Status == status);
            if (settlementId is not null) query = query.Where(m => m.SettlementId == settlementId);

            var measures = await query.OrderByDescending(m => m.Priority).Take(500).ToListAsync();
            return Results.Ok(measures.Select(ToDto));
        });

        // Ручное добавление меры
        group.MapPost("/", async (CreateMeasureRequest request, AppDbContext db) =>
        {
            if (string.IsNullOrWhiteSpace(request.Title) || string.IsNullOrWhiteSpace(request.Module))
                return Results.BadRequest(new { error = "Title и Module обязательны" });

            var settlement = await db.Settlements.FindAsync(request.SettlementId);
            if (settlement is null)
                return Results.BadRequest(new { error = $"НП {request.SettlementId} не найден" });

            var score = await db.SettlementMetrics
                .Where(m => m.SettlementId == settlement.Id && m.Module == request.Module)
                .OrderByDescending(m => m.UpdatedAt)
                .Select(m => (double?)m.Value)
                .FirstOrDefaultAsync() ?? 0;

            var measure = new PreventiveMeasure
            {
                SettlementId = settlement.Id,
                Settlement = settlement,
                Module = request.Module.Trim(),
                Title = request.Title.Trim(),
                Description = request.Description?.Trim(),
                Priority = ComputePriority(score, settlement.Population)
            };
            db.PreventiveMeasures.Add(measure);
            await db.SaveChangesAsync();
            return Results.Ok(ToDto(measure));
        });

        // Генерация черновиков по правилам из текущих скоров (Admin)
        group.MapPost("/generate", async (GenerateMeasuresRequest request, AppDbContext db) =>
        {
            if (request.Module != "flood-risk")
                return Results.BadRequest(new { error = "Генерация пока реализована только для module=flood-risk" });

            var period = request.Period ?? "";
            var scores = await db.SettlementMetrics
                .Where(m => m.Module == request.Module && m.MetricKey == request.MetricKey
                    && (period == "" || m.Period == period))
                .Join(db.Settlements, m => m.SettlementId, s => s.Id,
                    (m, s) => new { Settlement = s, m.Value })
                .ToListAsync();

            var existing = await db.PreventiveMeasures
                .Where(m => m.Module == request.Module && m.Status != MeasureStatus.Rejected)
                .Select(m => new { m.SettlementId, m.Title })
                .ToListAsync();
            var existingKeys = existing.Select(e => (e.SettlementId, e.Title)).ToHashSet();

            var created = 0;
            foreach (var row in scores)
            {
                foreach (var (minScore, title) in FloodRules)
                {
                    if (row.Value < minScore || existingKeys.Contains((row.Settlement.Id, title))) continue;
                    db.PreventiveMeasures.Add(new PreventiveMeasure
                    {
                        SettlementId = row.Settlement.Id,
                        Module = request.Module,
                        Title = title,
                        Description = $"Черновик по правилу «скор ≥ {minScore}» (скор {row.Value:F0})",
                        Priority = ComputePriority(row.Value, row.Settlement.Population)
                    });
                    existingKeys.Add((row.Settlement.Id, title));
                    created++;
                }
            }

            await db.SaveChangesAsync();
            return Results.Ok(new { created });
        }).RequireAuthorization(policy => policy.RequireRole(Roles.Admin));

        // Решение человека: утвердить / отклонить / выполнено
        group.MapPut("/{id:long}/status", async (long id, ChangeMeasureStatusRequest request, ClaimsPrincipal principal, AppDbContext db) =>
        {
            if (!MeasureStatus.All.Contains(request.Status))
                return Results.BadRequest(new { error = $"Статус должен быть одним из: {string.Join(", ", MeasureStatus.All)}" });

            var measure = await db.PreventiveMeasures.Include(m => m.Settlement).FirstOrDefaultAsync(m => m.Id == id);
            if (measure is null) return Results.NotFound();

            var userId = principal.GetUserId();
            if (userId is null) return Results.Unauthorized();
            var user = await db.Users.FindAsync(userId.Value);

            measure.Status = request.Status;
            measure.Note = request.Note?.Trim();
            measure.DecidedByUserId = userId;
            measure.DecidedByName = user?.DisplayName;
            measure.DecidedAt = DateTimeOffset.UtcNow;
            await db.SaveChangesAsync();
            return Results.Ok(ToDto(measure));
        });
    }

    /// <summary>Скор × lg(население): «Петропавловск 70» важнее «разъезд 90».</summary>
    private static double ComputePriority(double score, int? population) =>
        Math.Round(score * Math.Log10(Math.Max(population ?? 10, 10)), 1);
}
