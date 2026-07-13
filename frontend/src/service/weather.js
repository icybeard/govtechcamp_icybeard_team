// Живая погода по областям (Open-Meteo, без ключа): текущие температура/влажность/ветер
// + осадки за 7 прошлых дней и прогноз на сегодня. Используется обеими картами.

let centroidsCache = null;

export function degToCompass(deg) {
    const dirs = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];
    return dirs[Math.round(deg / 45) % 8];
}

function centroid(feature) {
    // центр bbox внешнего кольца — достаточно для стрелки ветра
    let minLat = 90,
        maxLat = -90,
        minLon = 180,
        maxLon = -180;
    const rings = feature.geometry.type === 'MultiPolygon' ? feature.geometry.coordinates.flat(1) : feature.geometry.coordinates;
    for (const ring of rings) {
        for (const [lon, lat] of ring) {
            minLat = Math.min(minLat, lat);
            maxLat = Math.max(maxLat, lat);
            minLon = Math.min(minLon, lon);
            maxLon = Math.max(maxLon, lon);
        }
    }
    return { lat: (minLat + maxLat) / 2, lon: (minLon + maxLon) / 2 };
}

async function regionCentroids() {
    if (centroidsCache) return centroidsCache;
    const geo = await (await fetch('/geo/kz-regions.geojson')).json();
    centroidsCache = geo.features.map((f) => ({ iso: f.properties.shapeISO, name: f.properties.shapeName, ...centroid(f) }));
    return centroidsCache;
}

/**
 * Возвращает { updatedAt, regions: { iso: { iso, name, lat, lon, temp, humidity,
 * windSpeed, windDir, precip7d, precip24h, forecast24h, dryDays } } }.
 */
export async function fetchRegionWeather() {
    const regions = await regionCentroids();
    const params = new URLSearchParams({
        latitude: regions.map((r) => r.lat.toFixed(3)).join(','),
        longitude: regions.map((r) => r.lon.toFixed(3)).join(','),
        current: 'temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m',
        daily: 'precipitation_sum',
        past_days: '7',
        forecast_days: '1',
        timezone: 'UTC'
    });
    const payload = await (await fetch(`https://api.open-meteo.com/v1/forecast?${params}`)).json();

    const result = {};
    payload.forEach((w, i) => {
        const daily = w.daily.precipitation_sum; // [7 прошлых дней, сегодня(прогноз)]
        const pastDays = daily.slice(0, 7);
        const precip7d = pastDays.reduce((s, v) => s + (v ?? 0), 0);
        let dryDays = 0;
        for (let d = pastDays.length - 1; d >= 0 && (pastDays[d] ?? 0) < 1; d--) dryDays++;
        result[regions[i].iso] = {
            ...regions[i],
            temp: w.current.temperature_2m,
            humidity: w.current.relative_humidity_2m,
            windSpeed: w.current.wind_speed_10m,
            windDir: w.current.wind_direction_10m,
            precip7d: Math.round(precip7d * 10) / 10,
            precip24h: Math.round((pastDays[6] ?? 0) * 10) / 10,
            forecast24h: Math.round((daily[7] ?? 0) * 10) / 10,
            dryDays
        };
    });
    return {
        updatedAt: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
        regions: result
    };
}

/** Стрелки ветра для карты: markers-совместимые объекты. */
export function windMarkers(regions, tooltipFor) {
    return Object.values(regions).map((w) => ({
        lat: w.lat,
        lon: w.lon,
        html: `<span style="display:inline-block;transform:rotate(${w.windDir + 180}deg);font-size:18px;color:#1e293b;text-shadow:0 0 3px #fff">↑</span>`,
        tooltip: tooltipFor(w)
    }));
}
