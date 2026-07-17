using System.Globalization;
using System.Security.Claims;
using GovTech.Api.Auth;
using GovTech.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Modules;

public record DatasetFileDto(long Id, string FileName, string Kind, string Period, long Size,
    string? Note, int? IngestedRows, string? UploadedByName, DateTimeOffset UploadedAt);

/// <summary>
/// Страница «Данные»: загрузка датасетов для обучения/пересчёта, реестр и удаление.
/// Kind=flood-scores (CSV формата scripts/load_scores.py) сразу ингестируется в
/// SettlementMetrics указанного сезона — карта паводков пересчитывается без
/// ML-окружения. Остальные типы складываются в каталог для офлайн-пайплайна.
/// </summary>
public static class DatasetEndpoints
{
    private static readonly string[] Kinds = ["flood-scores", "settlements", "fire-ml", "winter-districts", "training-raw"];
    private static readonly string[] AllowedExtensions = [".csv", ".json"];
    private const long MaxSizeBytes = 50 * 1024 * 1024;

    public static void MapDatasetEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/datasets").WithTags("Datasets").RequireAuthorization();

        static DatasetFileDto ToDto(DatasetFile d) => new(
            d.Id, d.FileName, d.Kind, d.Period, d.Size, d.Note, d.IngestedRows, d.UploadedByName, d.UploadedAt);

        // Реестр наборов — виден всем авторизованным
        group.MapGet("/", async (AppDbContext db) =>
        {
            var files = await db.DatasetFiles.OrderByDescending(d => d.UploadedAt).Take(200).ToListAsync();
            return Results.Ok(files.Select(ToDto));
        });

        // Загрузка (Admin). Форму читаем вручную — без антифорджери-инфраструктуры MVC
        group.MapPost("/upload", async (HttpRequest http, ClaimsPrincipal principal, AppDbContext db,
            IWebHostEnvironment env, IConfiguration config) =>
        {
            if (!http.HasFormContentType)
                return Results.BadRequest(new { error = "Ожидается multipart/form-data с полем file" });

            var form = await http.ReadFormAsync();
            var file = form.Files.GetFile("file");
            var kind = form["kind"].ToString().Trim();
            var period = form["period"].ToString().Trim();
            var note = form["note"].ToString().Trim();

            if (file is null || file.Length == 0)
                return Results.BadRequest(new { error = "Файл пуст или не передан" });
            if (file.Length > MaxSizeBytes)
                return Results.BadRequest(new { error = "Файл больше 50 МБ" });
            if (!Kinds.Contains(kind))
                return Results.BadRequest(new { error = $"kind должен быть одним из: {string.Join(", ", Kinds)}" });

            var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
            if (!AllowedExtensions.Contains(extension))
                return Results.BadRequest(new { error = "Поддерживаются только .csv и .json" });

            // на диске файл живёт под GUID-именем: оригинальное может содержать пути/спецсимволы
            var dir = config["Datasets:Path"] ?? Path.Combine(env.ContentRootPath, "data", "uploads");
            Directory.CreateDirectory(dir);
            var storedPath = Path.Combine(dir, $"{Guid.NewGuid():N}{extension}");
            await using (var stream = File.Create(storedPath))
                await file.CopyToAsync(stream);

            int? ingested = null;
            if (kind == "flood-scores")
            {
                var (error, updated) = await IngestFloodScores(storedPath, period, db);
                if (error is not null)
                {
                    File.Delete(storedPath);
                    return Results.BadRequest(new { error });
                }
                ingested = updated;
            }

            var userId = principal.GetUserId();
            var user = userId is null ? null : await db.Users.FindAsync(userId.Value);
            var dataset = new DatasetFile
            {
                FileName = Path.GetFileName(file.FileName),
                Kind = kind,
                Period = period,
                Size = file.Length,
                Note = string.IsNullOrEmpty(note) ? null : note,
                StoredPath = storedPath,
                IngestedRows = ingested,
                UploadedByName = user?.DisplayName
            };
            db.DatasetFiles.Add(dataset);
            await db.SaveChangesAsync();
            return Results.Ok(ToDto(dataset));
        }).RequireAuthorization(policy => policy.RequireRole(Roles.Admin));

        // Удаление из реестра вместе с файлом (Admin). Ингестированные метрики не откатываем.
        group.MapDelete("/{id:long}", async (long id, AppDbContext db) =>
        {
            var dataset = await db.DatasetFiles.FindAsync(id);
            if (dataset is null) return Results.NotFound();
            try
            {
                if (File.Exists(dataset.StoredPath)) File.Delete(dataset.StoredPath);
            }
            catch (IOException)
            {
                /* реестр важнее файла-сироты: запись удаляем в любом случае */
            }
            db.DatasetFiles.Remove(dataset);
            await db.SaveChangesAsync();
            return Results.NoContent();
        }).RequireAuthorization(policy => policy.RequireRole(Roles.Admin));
    }

    /// <summary>
    /// CSV name,lat,lon,score[,factors_json] → upsert SettlementMetrics (flood-risk,
    /// risk_score, period). Сопоставление как в scripts/load_scores.py: по имени,
    /// тёзки различаются ближайшими координатами.
    /// </summary>
    private static async Task<(string? Error, int Updated)> IngestFloodScores(string path, string period, AppDbContext db)
    {
        var rows = CsvFile.Read(path).ToList();
        if (rows.Count < 2) return ("CSV пуст или без строк данных", 0);

        var header = rows[0];
        int Col(string name) => Array.IndexOf(header, name);
        int nameCol = Col("name"), latCol = Col("lat"), lonCol = Col("lon"), scoreCol = Col("score"), factorsCol = Col("factors_json");
        if (nameCol < 0 || latCol < 0 || lonCol < 0 || scoreCol < 0)
            return ("Нужны колонки name, lat, lon, score (опционально factors_json) — формат scripts/load_scores.py", 0);

        var settlements = await db.Settlements.ToListAsync();
        var byName = settlements
            .GroupBy(s => s.Name.Trim().ToLowerInvariant())
            .ToDictionary(g => g.Key, g => g.ToList());

        var existing = await db.SettlementMetrics
            .Where(m => m.Module == "flood-risk" && m.MetricKey == "risk_score" && m.Period == period)
            .ToDictionaryAsync(m => m.SettlementId);

        var updated = 0;
        var matched = new HashSet<int>();
        foreach (var row in rows.Skip(1))
        {
            var maxCol = Math.Max(scoreCol, Math.Max(latCol, Math.Max(lonCol, nameCol)));
            if (row.Length <= maxCol) continue;
            if (!byName.TryGetValue(row[nameCol].Trim().ToLowerInvariant(), out var candidates)) continue;
            if (!double.TryParse(row[latCol], CultureInfo.InvariantCulture, out var lat)
                || !double.TryParse(row[lonCol], CultureInfo.InvariantCulture, out var lon)
                || !double.TryParse(row[scoreCol], CultureInfo.InvariantCulture, out var score)) continue;

            var settlement = candidates.MinBy(s => (s.Lat - lat) * (s.Lat - lat) + (s.Lon - lon) * (s.Lon - lon))!;
            if (!matched.Add(settlement.Id)) continue;

            var factorsJson = factorsCol >= 0 && factorsCol < row.Length && !string.IsNullOrWhiteSpace(row[factorsCol])
                ? row[factorsCol]
                : null;
            if (existing.TryGetValue(settlement.Id, out var metric))
            {
                metric.Value = score;
                metric.FactorsJson = factorsJson;
                metric.UpdatedAt = DateTimeOffset.UtcNow;
            }
            else
            {
                db.SettlementMetrics.Add(new SettlementMetric
                {
                    SettlementId = settlement.Id,
                    Module = "flood-risk",
                    MetricKey = "risk_score",
                    Period = period,
                    Value = score,
                    FactorsJson = factorsJson
                });
            }
            updated++;
        }

        if (updated == 0) return ("Ни одна строка не сопоставлена с НП в БД (совпадение по колонке name)", 0);
        await db.SaveChangesAsync();
        return (null, updated);
    }
}
