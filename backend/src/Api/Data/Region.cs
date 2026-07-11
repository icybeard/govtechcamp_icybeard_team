namespace GovTech.Api.Data;

/// <summary>Область/город РК. IsoCode совпадает с shapeISO в frontend/public/geo/kz-regions.geojson.</summary>
public class Region
{
    public int Id { get; set; }
    public required string IsoCode { get; set; }
    public required string NameEn { get; set; }
    public required string NameRu { get; set; }
    public List<RegionMetric> Metrics { get; set; } = [];
}
