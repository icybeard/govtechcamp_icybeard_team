namespace GovTech.Api.Data;

/// <summary>
/// Реестр загруженных наборов данных (страница «Данные»). Файл лежит на диске
/// (каталог Datasets:Path, имя — GUID), в БД — метаданные и кто загрузил.
/// Kind=flood-scores дополнительно ингестируется в SettlementMetrics —
/// «пересчёт рисков» без ML-окружения; остальные типы использует
/// офлайн-пайплайн ML (make-цели).
/// </summary>
public class DatasetFile
{
    public long Id { get; set; }
    public required string FileName { get; set; }
    public required string Kind { get; set; }
    public string Period { get; set; } = "";
    public long Size { get; set; }
    public string? Note { get; set; }
    public required string StoredPath { get; set; }
    /// <summary>Сколько строк легло в БД при ингесте (null — тип без ингеста).</summary>
    public int? IngestedRows { get; set; }
    public string? UploadedByName { get; set; }
    public DateTimeOffset UploadedAt { get; set; } = DateTimeOffset.UtcNow;
}
