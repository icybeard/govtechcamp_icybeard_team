namespace GovTech.Api.Data;

/// <summary>
/// Превентивная мера для НП (паводки) или района ADM2 (пожары, зима).
/// Ровно одна из привязок заполнена: SettlementId — FK на НП; DistrictId —
/// shapeID геослоя районов (районы в БД не заведены, скоры district-мер
/// приходят с фронта при генерации). Система генерирует черновики (Proposed),
/// финальное решение принимает человек (Approved/Rejected) — human-in-the-loop
/// с аудиторским следом (кто и когда решил).
/// </summary>
public class PreventiveMeasure
{
    public long Id { get; set; }
    public int? SettlementId { get; set; }
    public Settlement? Settlement { get; set; }
    public string? DistrictId { get; set; }
    public string? DistrictName { get; set; }
    public required string Module { get; set; }
    public required string Title { get; set; }
    public string? Description { get; set; }
    public string Status { get; set; } = MeasureStatus.Proposed;
    /// <summary>Приоритет = скор риска × lg(население): чем выше, тем раньше в очереди.</summary>
    public double Priority { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public Guid? DecidedByUserId { get; set; }
    public string? DecidedByName { get; set; }
    public DateTimeOffset? DecidedAt { get; set; }
    public string? Note { get; set; }
}

public static class MeasureStatus
{
    public const string Proposed = "Proposed";
    public const string Approved = "Approved";
    public const string Rejected = "Rejected";
    public const string Done = "Done";

    public static readonly string[] All = [Proposed, Approved, Rejected, Done];
}
