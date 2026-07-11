using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Data;

public static class DbSeeder
{
    // ISO-коды совпадают с shapeISO в frontend/public/geo/kz-regions.geojson
    // (границы geoBoundaries 2017 г., 16 единиц — заменить вместе с geojson при переходе на границы-2022).
    private static readonly (string Iso, string En, string Ru)[] KzRegions =
    [
        ("KZ-AKM", "Akmola Region", "Акмолинская область"),
        ("KZ-AKT", "Aktobe Region", "Актюбинская область"),
        ("KZ-ALA", "Almaty", "г. Алматы"),
        ("KZ-ALM", "Almaty Region", "Алматинская область"),
        ("KZ-AST", "Astana", "г. Астана"),
        ("KZ-ATY", "Atyrau Region", "Атырауская область"),
        ("KZ-KAR", "Karaganda Region", "Карагандинская область"),
        ("KZ-KUS", "Kostanay Region", "Костанайская область"),
        ("KZ-KZY", "Kyzylorda Region", "Кызылординская область"),
        ("KZ-MAN", "Mangystau Region", "Мангистауская область"),
        ("KZ-PAV", "Pavlodar Region", "Павлодарская область"),
        ("KZ-SEV", "North Kazakhstan Region", "Северо-Казахстанская область"),
        ("KZ-VOS", "East Kazakhstan Region", "Восточно-Казахстанская область"),
        ("KZ-YUZ", "South Kazakhstan Region", "Туркестанская (Южно-Казахстанская) область"),
        ("KZ-ZAP", "West Kazakhstan Region", "Западно-Казахстанская область"),
        ("KZ-ZHA", "Jambyl Region", "Жамбылская область")
    ];

    public static async Task SeedAsync(AppDbContext db, IConfiguration configuration)
    {
        foreach (var (iso, en, ru) in KzRegions)
        {
            if (!await db.Regions.AnyAsync(r => r.IsoCode == iso))
            {
                db.Regions.Add(new Region { IsoCode = iso, NameEn = en, NameRu = ru });
            }
        }

        await SeedSuperUserAsync(db, configuration);

        await db.SaveChangesAsync();
    }

    /// <summary>
    /// Суперпользователь из .env / env (SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD):
    /// создаётся, если отсутствует; существующему аккаунту гарантируется роль Admin.
    /// Пароль существующего пользователя не перезаписывается.
    /// </summary>
    private static async Task SeedSuperUserAsync(AppDbContext db, IConfiguration configuration)
    {
        var email = (configuration["Seed:AdminEmail"] ?? "admin@icybeard.local").Trim().ToLowerInvariant();
        var superUser = await db.Users.FirstOrDefaultAsync(u => u.Email == email);

        if (superUser is null)
        {
            var password = configuration["Seed:AdminPassword"]
                ?? throw new InvalidOperationException(
                    "Seed:AdminPassword is not configured — задайте SEED_ADMIN_PASSWORD в .env (см. .env.example)");
            db.Users.Add(new User
            {
                Email = email,
                DisplayName = "Admin",
                Role = Roles.Admin,
                PasswordHash = BCrypt.Net.BCrypt.HashPassword(password)
            });
        }
        else if (superUser.Role != Roles.Admin)
        {
            superUser.Role = Roles.Admin;
        }
    }
}
