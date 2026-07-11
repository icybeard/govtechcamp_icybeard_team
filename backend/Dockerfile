FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY src/Api/GovTech.Api.csproj src/Api/
RUN dotnet restore src/Api/GovTech.Api.csproj
COPY src/ src/
RUN dotnet publish src/Api/GovTech.Api.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app .
EXPOSE 8080
ENTRYPOINT ["dotnet", "GovTech.Api.dll"]
