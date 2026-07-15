# Контекст сборки — корень репозитория (см. docker-compose.yml):
# в образ запекаются CSV пилота, чтобы жюри получало данные без скриптов.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY backend/src/Api/GovTech.Api.csproj src/Api/
RUN dotnet restore src/Api/GovTech.Api.csproj
COPY backend/src/ src/
RUN dotnet publish src/Api/GovTech.Api.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app .
COPY data/raw/settlements_kz-sev.csv seed-data/
COPY data/processed/scores_*.csv seed-data/
COPY data/processed/winter_regions.csv seed-data/
EXPOSE 8080
ENTRYPOINT ["dotnet", "GovTech.Api.dll"]
