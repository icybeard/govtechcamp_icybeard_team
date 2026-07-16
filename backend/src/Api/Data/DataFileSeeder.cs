using System.Globalization;
using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Data;

/// <summary>
/// Первичная загрузка данных пилота из CSV при пустой БД: НП СКО + скоры
/// (актуальные и сезоны 2010–2026). Нужна, чтобы жюри получало рабочее
/// приложение сразу после `make up`, без python-скриптов.
/// В docker-образе CSV лежат в /app/seed-data (см. backend/Dockerfile);
/// при локальном запуске ищутся вверх по дереву в data/raw и data/processed.
/// </summary>
public static class DataFileSeeder
{
    private const string RegionIso = "KZ-SEV";
    private const string Module = "flood-risk";
    private const string MetricKey = "risk_score";

    public static async Task SeedAsync(AppDbContext db, ILogger logger)
    {
        if (await db.Settlements.AnyAsync()) return;

        var (settlementsCsv, scoresDir) = FindDataFiles();
        if (settlementsCsv is null || scoresDir is null)
        {
            logger.LogInformation("Seed-данные пилота не найдены — карта будет пустой до загрузки скриптами");
            return;
        }

        var region = await db.Regions.FirstOrDefaultAsync(r => r.IsoCode == RegionIso);
        if (region is null) return;

        // НП: upsert по имени (тёзки схлопываются — как в scripts/load_settlements.py)
        var byName = new Dictionary<string, Settlement>();
        foreach (var row in CsvFile.Read(settlementsCsv).Skip(1))
        {
            if (row.Length < 4 || string.IsNullOrWhiteSpace(row[0])) continue;
            var name = row[0].Trim();
            var settlement = new Settlement
            {
                RegionId = region.Id,
                Name = name,
                Lat = double.Parse(row[1], CultureInfo.InvariantCulture),
                Lon = double.Parse(row[2], CultureInfo.InvariantCulture),
                Population = int.TryParse(row[3], out var pop) ? pop : null
            };
            if (byName.TryAdd(name, settlement)) db.Settlements.Add(settlement);
        }
        await db.SaveChangesAsync();
        logger.LogInformation("Seed: {Count} НП из {File}", byName.Count, Path.GetFileName(settlementsCsv));

        // Скоры: актуальные (period='') + сезоны по годам
        var scoreFiles = new List<(string Path, string Period)>();
        var mlScores = Path.Combine(scoresDir, "scores_ml_kz-sev.csv");
        if (File.Exists(mlScores)) scoreFiles.Add((mlScores, ""));
        foreach (var file in Directory.GetFiles(scoresDir, "scores_2*_kz-sev.csv"))
        {
            var period = Path.GetFileName(file).Split('_')[1];
            scoreFiles.Add((file, period));
        }

        foreach (var (file, period) in scoreFiles)
        {
            foreach (var row in CsvFile.Read(file).Skip(1))
            {
                if (row.Length < 5 || !byName.TryGetValue(row[0].Trim(), out var settlement)) continue;
                db.SettlementMetrics.Add(new SettlementMetric
                {
                    Settlement = settlement,
                    Module = Module,
                    MetricKey = MetricKey,
                    Period = period,
                    Value = double.Parse(row[3], CultureInfo.InvariantCulture),
                    FactorsJson = string.IsNullOrWhiteSpace(row[4]) ? null : row[4]
                });
            }
        }
        await db.SaveChangesAsync();
        logger.LogInformation("Seed: скоры из {Count} файлов (актуальные + сезоны)", scoreFiles.Count);

        // Зимняя обстановка по областям: RegionMetric из winter_regions.csv (если файл есть).
        // Пакетная загрузка при пустой БД — как скоры паводка, без внешних HTTP-запросов.
        var winterCsv = Path.Combine(scoresDir, "winter_regions.csv");
        if (File.Exists(winterCsv))
        {
            var regionsByIso = await db.Regions.ToDictionaryAsync(r => r.IsoCode);
            var winterRows = CsvFile.Read(winterCsv).ToList();
            if (winterRows.Count > 1)
            {
                var header = winterRows[0];
                int Col(string name) => Array.IndexOf(header, name);
                int isoCol = Col("iso"), seasonCol = Col("season");
                string[] metricCols = { "risk_score", "idx_glaze", "idx_blizzard", "idx_snowload", "idx_cold" };
                foreach (var row in winterRows.Skip(1))
                {
                    if (isoCol < 0 || seasonCol < 0 || row.Length <= seasonCol) continue;
                    if (!regionsByIso.TryGetValue(row[isoCol].Trim(), out var reg)) continue;
                    var winterPeriod = row[seasonCol].Trim();
                    foreach (var mc in metricCols)
                    {
                        int c = Col(mc);
                        if (c < 0 || c >= row.Length || string.IsNullOrWhiteSpace(row[c])) continue;
                        db.RegionMetrics.Add(new RegionMetric
                        {
                            RegionId = reg.Id,
                            Module = "winter-risk",
                            MetricKey = mc,
                            Period = winterPeriod,
                            Value = double.Parse(row[c], CultureInfo.InvariantCulture)
                        });
                    }
                }
                await db.SaveChangesAsync();
                logger.LogInformation("Seed: winter-risk — региональные метрики из {File}", Path.GetFileName(winterCsv));
            }
        }
    }

    private static (string? Settlements, string? ScoresDir) FindDataFiles()
    {
        // 1) docker-образ: /app/seed-data (всё в одной папке)
        var baked = Path.Combine(AppContext.BaseDirectory, "seed-data");
        if (File.Exists(Path.Combine(baked, "settlements_kz-sev.csv")))
            return (Path.Combine(baked, "settlements_kz-sev.csv"), baked);

        // 2) локальный запуск: корень репозитория вверх по дереву
        var dir = new DirectoryInfo(Directory.GetCurrentDirectory());
        for (var i = 0; i < 5 && dir is not null; i++, dir = dir.Parent)
        {
            var settlements = Path.Combine(dir.FullName, "data", "raw", "settlements_kz-sev.csv");
            var scores = Path.Combine(dir.FullName, "data", "processed");
            if (File.Exists(settlements) && Directory.Exists(scores))
                return (settlements, scores);
        }
        return (null, null);
    }

}
