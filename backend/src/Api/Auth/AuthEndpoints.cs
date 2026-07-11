using System.Security.Claims;
using GovTech.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Auth;

public record RegisterRequest(string Email, string Password, string DisplayName);
public record LoginRequest(string Email, string Password);
public record UserDto(Guid Id, string Email, string DisplayName, string Role);
public record AuthResponse(string Token, UserDto User);

public static class AuthEndpoints
{
    public static UserDto ToDto(this User user) => new(user.Id, user.Email, user.DisplayName, user.Role);

    public static Guid? GetUserId(this ClaimsPrincipal principal)
    {
        var raw = principal.FindFirstValue(ClaimTypes.NameIdentifier);
        return Guid.TryParse(raw, out var id) ? id : null;
    }

    public static void MapAuthEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/auth").WithTags("Auth");

        group.MapPost("/register", async (RegisterRequest request, AppDbContext db, JwtTokenService jwt) =>
        {
            if (string.IsNullOrWhiteSpace(request.Email) || !request.Email.Contains('@'))
                return Results.BadRequest(new { error = "Некорректный email" });
            if (string.IsNullOrWhiteSpace(request.Password) || request.Password.Length < 8)
                return Results.BadRequest(new { error = "Пароль должен быть не короче 8 символов" });
            if (string.IsNullOrWhiteSpace(request.DisplayName))
                return Results.BadRequest(new { error = "Имя обязательно" });

            var email = request.Email.Trim().ToLowerInvariant();
            if (await db.Users.AnyAsync(u => u.Email == email))
                return Results.Conflict(new { error = "Пользователь с таким email уже существует" });

            var user = new User
            {
                Email = email,
                DisplayName = request.DisplayName.Trim(),
                PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.Password),
                Role = Roles.Analyst
            };
            db.Users.Add(user);
            await db.SaveChangesAsync();

            return Results.Ok(new AuthResponse(jwt.CreateToken(user), user.ToDto()));
        });

        group.MapPost("/login", async (LoginRequest request, AppDbContext db, JwtTokenService jwt) =>
        {
            var email = request.Email.Trim().ToLowerInvariant();
            var user = await db.Users.FirstOrDefaultAsync(u => u.Email == email);
            if (user is null || !BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash))
                return Results.Json(new { error = "Неверный email или пароль" }, statusCode: StatusCodes.Status401Unauthorized);

            return Results.Ok(new AuthResponse(jwt.CreateToken(user), user.ToDto()));
        });

        group.MapGet("/me", async (ClaimsPrincipal principal, AppDbContext db) =>
        {
            var userId = principal.GetUserId();
            if (userId is null) return Results.Unauthorized();

            var user = await db.Users.FindAsync(userId.Value);
            return user is null ? Results.Unauthorized() : Results.Ok(user.ToDto());
        }).RequireAuthorization();
    }
}
