namespace GovTech.Api.Data;

/// <summary>
/// Метрика НП из ML-пайплайна. FactorsJson — top-факторы SHAP для панели «Почему»:
/// [{"name":"Снегозапас 132% нормы","impact":0.31}, ...].
/// </summary>
public class SettlementMetric
{
    public long Id { get; set; }
    public int SettlementId { get; set; }
    public Settlement? Settlement { get; set; }
    public required string Module { get; set; }
    public required string MetricKey { get; set; }
    public double Value { get; set; }
    public string Period { get; set; } = "";
    public string? FactorsJson { get; set; }
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
}
