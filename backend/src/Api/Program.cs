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
    ["Seed:AdminPassword"] = FromEnv("SEED_ADMIN_PASSWORD"),
    ["Firms:MapKey"] = FromEnv("FIRMS_MAP_KEY")
};
builder.Configuration.AddInMemoryCollection(
    envOverrides.Where(kv => !string.IsNullOrWhiteSpace(kv.Value)).ToDictionary(kv => kv.Key, kv => kv.Value));

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Default")));

builder.Services.AddSingleton<JwtTokenService>();
builder.Services.AddHttpClient();

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

// OpenAPI-документ (/openapi/v1.json) + Bearer-схема, чтобы в Swagger UI работала
// кнопка Authorize: токен из POST /api/auth/login подставляется во все запросы
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer((document, _, _) =>
    {
        document.Info ??= new Microsoft.OpenApi.OpenApiInfo();
        document.Info.Title = "IcyBeard GovTech API";
        document.Info.Description = "Риск-скоринг НП и районов (паводки, пожары, зима), очередь превентивных мер. Авторизация: POST /api/auth/login → кнопка Authorize → вставить token.";
        document.Components ??= new Microsoft.OpenApi.OpenApiComponents();
        document.Components.SecuritySchemes ??= new Dictionary<string, Microsoft.OpenApi.IOpenApiSecurityScheme>();
        document.Components.SecuritySchemes["Bearer"] = new Microsoft.OpenApi.OpenApiSecurityScheme
        {
            Type = Microsoft.OpenApi.SecuritySchemeType.Http,
            Scheme = "bearer",
            BearerFormat = "JWT"
        };
        document.Security = [new Microsoft.OpenApi.OpenApiSecurityRequirement
        {
            [new Microsoft.OpenApi.OpenApiSecuritySchemeReference("Bearer", document)] = []
        }];
        return Task.CompletedTask;
    });
});

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
        await DataFileSeeder.SeedAsync(db, app.Logger);
    }
    catch (Exception ex)
    {
        app.Logger.LogError(ex, "Не удалось применить миграции/сид. Проверьте, что PostgreSQL запущен: docker compose up -d");
    }
}

// Swagger доступен и в проде (dc.jurek.kz/swagger): документация API — часть
// сдаваемых артефактов, все мутирующие эндпоинты и так под JWT-авторизацией
app.MapOpenApi();
app.UseSwaggerUI(options =>
{
    options.SwaggerEndpoint("/openapi/v1.json", "IcyBeard GovTech API v1");
    options.DocumentTitle = "IcyBeard GovTech API — Swagger";
});

app.UseCors();
app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/api/health", () => Results.Ok(new { status = "ok" }));

app.MapAuthEndpoints();
app.MapAccountEndpoints();
app.MapRegionEndpoints();
app.MapSettlementEndpoints();
app.MapMeasureEndpoints();
app.MapFireEndpoints();
app.MapDatasetEndpoints();

app.Run();
