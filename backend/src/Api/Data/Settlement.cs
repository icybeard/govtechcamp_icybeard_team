namespace GovTech.Api.Data;

/// <summary>Населённый пункт — объект скоринга И-6 (уровень ниже области).</summary>
public class Settlement
{
    public int Id { get; set; }
    public int RegionId { get; set; }
    public Region? Region { get; set; }
    public required string Name { get; set; }
    public string? KatoCode { get; set; }
    public double Lat { get; set; }
    public double Lon { get; set; }
    public int? Population { get; set; }
    public List<SettlementMetric> Metrics { get; set; } = [];
}
