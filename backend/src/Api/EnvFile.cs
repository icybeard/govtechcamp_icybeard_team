namespace GovTech.Api;

/// <summary>
/// Минимальный загрузчик .env: ищет файл вверх от текущей директории (до 5 уровней),
/// чтобы `dotnet run` из backend/src/Api находил .env в корне репозитория.
/// Реальные переменные окружения имеют приоритет над значениями из файла.
/// </summary>
public static class EnvFile
{
    public static Dictionary<string, string> Load()
    {
        var dir = new DirectoryInfo(Directory.GetCurrentDirectory());
        for (var i = 0; i < 5 && dir is not null; i++, dir = dir.Parent)
        {
            var path = Path.Combine(dir.FullName, ".env");
            if (File.Exists(path))
            {
                return Parse(File.ReadAllLines(path));
            }
        }
        return [];
    }

    private static Dictionary<string, string> Parse(string[] lines)
    {
        var result = new Dictionary<string, string>();
        foreach (var raw in lines)
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#')) continue;

            var separator = line.IndexOf('=');
            if (separator <= 0) continue;

            var key = line[..separator].Trim();
            var value = line[(separator + 1)..].Trim().Trim('"', '\'');
            result[key] = value;
        }
        return result;
    }
}
