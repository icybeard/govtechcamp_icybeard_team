using System.Text;
using GovTech.Api;
using GovTech.Api.Account;
using GovTech.Api.Auth;
using GovTech.Api.Data;
using GovTech.Api.Modules;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

// .env из корня репозитория (для локального запуска; в docker значения приходят через environment).
// Приоритет: реальная переменная окружения > .env > appsettings.
var envFile = EnvFile.Load();
string? FromEnv(string key) => Environment.GetEnvironmentVariable(key) ?? envFile.GetValueOrDefault(key);
var envOverrides = new Dictionary<string, string?>
{
    ["Jwt:Key"] = FromEnv("JWT_KEY"),
    ["Seed:AdminEmail"] = FromEnv("SEED_ADMIN_EMAIL"),
    ["Seed:AdminPassword"] = FromEnv("SEED_ADMIN_PASSWORD")
};
builder.Configuration.AddInMemoryCollection(
    envOverrides.Where(kv => !string.IsNullOrWhiteSpace(kv.Value)).ToDictionary(kv => kv.Key, kv => kv.Value));

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Default")));

builder.Services.AddSingleton<JwtTokenService>();

var jwtKey = builder.Configuration["Jwt:Key"]
    ?? throw new InvalidOperationException("Jwt:Key is not configured (env JWT__KEY or appsettings)");

builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = builder.Configuration["Jwt:Issuer"],
            ValidateAudience = true,
            ValidAudience = builder.Configuration["Jwt:Audience"],
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey)),
            ClockSkew = TimeSpan.FromMinutes(1)
        };
    });

builder.Services.AddAuthorization();

builder.Services.AddCors(options => options.AddDefaultPolicy(policy =>
    policy.WithOrigins(builder.Configuration["Cors:Origins"]?.Split(';') ?? ["http://localhost:5173"])
        .AllowAnyHeader()
        .AllowAnyMethod()));

builder.Services.AddOpenApi();

var app = builder.Build();

// Автоматическая миграция и сид справочников при старте (удобно для команды из двух человек;
// для продакшена заменить на явный шаг деплоя).
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    try
    {
        await db.Database.MigrateAsync();
        await DbSeeder.SeedAsync(db, app.Configuration);
    }
    catch (Exception ex)
    {
        app.Logger.LogError(ex, "Не удалось применить миграции/сид. Проверьте, что PostgreSQL запущен: docker compose up -d");
    }
}

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.UseCors();
app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/api/health", () => Results.Ok(new { status = "ok" }));

app.MapAuthEndpoints();
app.MapAccountEndpoints();
app.MapRegionEndpoints();

app.Run();
