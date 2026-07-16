namespace GovTech.Api.Data;

/// <summary>
/// Минимальный CSV-парсер с поддержкой кавычек ("" — экранирование):
/// factors_json содержит запятые. Общий для сидера и загрузки датасетов.
/// </summary>
public static class CsvFile
{
    public static IEnumerable<string[]> Read(string path)
    {
        foreach (var line in File.ReadLines(path))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            var fields = new List<string>();
            var current = new System.Text.StringBuilder();
            var inQuotes = false;
            for (var i = 0; i < line.Length; i++)
            {
                var c = line[i];
                if (inQuotes)
                {
                    if (c == '"' && i + 1 < line.Length && line[i + 1] == '"') { current.Append('"'); i++; }
                    else if (c == '"') inQuotes = false;
                    else current.Append(c);
                }
                else if (c == '"') inQuotes = true;
                else if (c == ',') { fields.Add(current.ToString()); current.Clear(); }
                else current.Append(c);
            }
            fields.Add(current.ToString());
            yield return fields.ToArray();
        }
    }
}
