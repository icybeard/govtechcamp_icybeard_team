namespace GovTech.Api.Data;

/// <summary>
/// Обогащение карты: одно числовое значение метрики для региона.
/// Module — код идеи ('flood-risk', 'fire-risk', 'poaching'), MetricKey — имя метрики
/// ('risk_score', 'incidents', ...), Period — опциональный срез ('2026-04').
/// </summary>
public class RegionMetric
{
    public long Id { get; set; }
    public int RegionId { get; set; }
    public Region? Region { get; set; }
    public required string Module { get; set; }
    public required string MetricKey { get; set; }
    public double Value { get; set; }
    public string Period { get; set; } = "";
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
}
