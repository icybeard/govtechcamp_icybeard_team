using System.Security.Claims;
using GovTech.Api.Auth;
using GovTech.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Modules;

public record MeasureDto(long Id, int? SettlementId, string SettlementName, string Module, string Title,
    string? Description, string Status, double Priority, string? DecidedByName, DateTimeOffset? DecidedAt, string? Note,
    string? DistrictId, string? DistrictName);

public record CreateMeasureRequest(int SettlementId, string Module, string Title, string? Description);

/// <summary>Скор района для генерации district-мер: районов в БД нет, значения приходят с фронта (ML/статические JSON).</summary>
public record DistrictScore(double Value, string Name);
public record GenerateMeasuresRequest(string Module, string MetricKey, string? Period, Dictionary<string, DistrictScore>? DistrictValues);
public record ChangeMeasureStatusRequest(string Status, string? Note);

public static class MeasureEndpoints
{
    // Правила генерации черновиков: порог скора → мера. Копия для отображения —
    // frontend/src/config/measureRules.js (синхронизировать при изменении).
    private static readonly (double MinScore, string Title)[] FloodRules =
    [
        (70, "Обследование дамб и водопропускных сооружений"),
        (70, "Актуализация плана эвакуации"),
        (40, "Очистка русла и водопропускных труб"),
        (20, "Усиленный мониторинг снегозапаса и уровня воды")
    ];

    // Пожары и зима — district-модули (ADM2): скоры приходят с фронта в DistrictValues
    private static readonly Dictionary<string, (double MinScore, string Title)[]> DistrictRules = new()
    {
        ["fire-risk"] =
        [
            (70, "Запрет на посещение лесов и противопожарный режим"),
            (60, "Усиленное патрулирование лесхозов и рейды"),
            (40, "Проверка минерализованных полос и опашка"),
            (20, "Информирование населения о пожарной опасности")
        ],
        ["winter-risk"] =
        [
            (60, "Резерв техники и ГСМ для расчистки дорог"),
            (50, "Пункты обогрева на трассах и план эвакуации"),
            (35, "Обработка дорог противогололёдными материалами"),
            (20, "Проверка снеговой нагрузки на кровлях соцобъектов")
        ]
    };

    public static void MapMeasureEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/measures").WithTags("Measures").RequireAuthorization();

        static MeasureDto ToDto(PreventiveMeasure m) => new(
            m.Id, m.SettlementId, m.Settlement?.Name ?? "", m.Module, m.Title,
            m.Description, m.Status, m.Priority, m.DecidedByName, m.DecidedAt, m.Note,
            m.DistrictId, m.DistrictName);

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

        // Генерация черновиков по правилам из текущих скоров (Admin).
        // flood-risk — по метрикам НП из БД; fire-risk/winter-risk — по скорам
        // районов из запроса (ML-прогноз / сезонный JSON, районов в БД нет).
        group.MapPost("/generate", async (GenerateMeasuresRequest request, AppDbContext db) =>
        {
            if (DistrictRules.TryGetValue(request.Module, out var districtRules))
                return await GenerateDistrictMeasures(request, districtRules, db);

            if (request.Module != "flood-risk")
                return Results.BadRequest(new { error = "Генерация поддерживает module=flood-risk, fire-risk, winter-risk" });

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

    /// <summary>Черновики district-мер: тот же порог-дедуп-цикл, что у паводков,
    /// но объект — район (shapeID), приоритет — сам скор (население района неизвестно).</summary>
    private static async Task<IResult> GenerateDistrictMeasures(
        GenerateMeasuresRequest request, (double MinScore, string Title)[] rules, AppDbContext db)
    {
        if (request.DistrictValues is null || request.DistrictValues.Count == 0)
            return Results.BadRequest(new { error = "Для district-модулей нужен districtValues: { shapeID: { value, name } }" });

        var existing = await db.PreventiveMeasures
            .Where(m => m.Module == request.Module && m.Status != MeasureStatus.Rejected && m.DistrictId != null)
            .Select(m => new { m.DistrictId, m.Title })
            .ToListAsync();
        var existingKeys = existing.Select(e => (e.DistrictId!, e.Title)).ToHashSet();

        var seasonSuffix = string.IsNullOrEmpty(request.Period) ? "" : $", сезон {request.Period}";
        var created = 0;
        foreach (var (districtId, score) in request.DistrictValues)
        {
            if (string.IsNullOrWhiteSpace(districtId) || string.IsNullOrWhiteSpace(score.Name)) continue;
            foreach (var (minScore, title) in rules)
            {
                if (score.Value < minScore || existingKeys.Contains((districtId, title))) continue;
                db.PreventiveMeasures.Add(new PreventiveMeasure
                {
                    DistrictId = districtId,
                    DistrictName = score.Name.Trim(),
                    Module = request.Module,
                    Title = title,
                    Description = $"Черновик по правилу «скор ≥ {minScore}» (скор {score.Value:F0}{seasonSuffix})",
                    Priority = Math.Round(score.Value, 1)
                });
                existingKeys.Add((districtId, title));
                created++;
            }
        }

        await db.SaveChangesAsync();
        return Results.Ok(new { created });
    }

    /// <summary>Скор × lg(население): «Петропавловск 70» важнее «разъезд 90».</summary>
    private static double ComputePriority(double score, int? population) =>
        Math.Round(score * Math.Log10(Math.Max(population ?? 10, 10)), 1);
}
