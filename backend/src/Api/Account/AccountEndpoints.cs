using System.Security.Claims;
using GovTech.Api.Auth;
using GovTech.Api.Data;

namespace GovTech.Api.Account;

public record UpdateProfileRequest(string DisplayName);
public record ChangePasswordRequest(string CurrentPassword, string NewPassword);

public static class AccountEndpoints
{
    public static void MapAccountEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/account").WithTags("Account").RequireAuthorization();

        group.MapPut("/profile", async (UpdateProfileRequest request, ClaimsPrincipal principal, AppDbContext db) =>
        {
            if (string.IsNullOrWhiteSpace(request.DisplayName))
                return Results.BadRequest(new { error = "Имя не может быть пустым" });

            var userId = principal.GetUserId();
            if (userId is null) return Results.Unauthorized();

            var user = await db.Users.FindAsync(userId.Value);
            if (user is null) return Results.Unauthorized();

            user.DisplayName = request.DisplayName.Trim();
            await db.SaveChangesAsync();
            return Results.Ok(user.ToDto());
        });

        group.MapPut("/password", async (ChangePasswordRequest request, ClaimsPrincipal principal, AppDbContext db) =>
        {
            if (string.IsNullOrWhiteSpace(request.NewPassword) || request.NewPassword.Length < 8)
                return Results.BadRequest(new { error = "Новый пароль должен быть не короче 8 символов" });

            var userId = principal.GetUserId();
            if (userId is null) return Results.Unauthorized();

            var user = await db.Users.FindAsync(userId.Value);
            if (user is null) return Results.Unauthorized();

            if (!BCrypt.Net.BCrypt.Verify(request.CurrentPassword, user.PasswordHash))
                return Results.BadRequest(new { error = "Текущий пароль неверен" });

            user.PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.NewPassword);
            await db.SaveChangesAsync();
            return Results.NoContent();
        });
    }
}
