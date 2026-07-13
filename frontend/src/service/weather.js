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

// Сетка ветра 2°×2° по Казахстану для анимации leaflet-velocity (u/v в м/с).
// Шаг 2°: 198 точек = 2 батча — укладываемся в минутный лимит бесплатного Open-Meteo
// (батч на N точек тарифицируется как N запросов); слой интерполирует между узлами.
const WIND_GRID = { latMin: 40, latMax: 56, lonMin: 46, lonMax: 88, step: 2 };
let windGridCache = null; // { at, data } — сетка тяжёлая (8 батчей), кэш на 15 минут

export async function fetchWindGrid() {
    if (windGridCache && Date.now() - windGridCache.at < 15 * 60 * 1000) return windGridCache.data;
    const lats = [];
    for (let la = WIND_GRID.latMax; la >= WIND_GRID.latMin; la -= WIND_GRID.step) lats.push(la);
    const lons = [];
    for (let lo = WIND_GRID.lonMin; lo <= WIND_GRID.lonMax; lo += WIND_GRID.step) lons.push(lo);
    const points = lats.flatMap((la) => lons.map((lo) => [la, lo]));

    const speeds = new Array(points.length);
    const dirs = new Array(points.length);
    for (let i = 0; i < points.length; i += 100) {
        const batch = points.slice(i, i + 100);
        const params = new URLSearchParams({
            latitude: batch.map((p) => p[0]).join(','),
            longitude: batch.map((p) => p[1]).join(','),
            current: 'wind_speed_10m,wind_direction_10m',
            wind_speed_unit: 'ms'
        });
        // 429 у бесплатного API — обычное дело: до 5 попыток с экспоненциальной паузой
        let payload = null;
        for (let attempt = 0; attempt < 5; attempt++) {
            const response = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`);
            if (response.ok) {
                payload = await response.json();
                break;
            }
            await new Promise((r) => setTimeout(r, 1500 * 2 ** attempt));
        }
        if (!payload) throw new Error('Open-Meteo: превышен лимит запросов');
        (Array.isArray(payload) ? payload : [payload]).forEach((w, j) => {
            speeds[i + j] = w.current.wind_speed_10m;
            dirs[i + j] = w.current.wind_direction_10m;
        });
        await new Promise((r) => setTimeout(r, 500)); // бережём бесплатный API
    }

    // метеонаправление «откуда дует» → компоненты «куда»: u = −v·sin, v = −v·cos
    const u = speeds.map((s, i) => -s * Math.sin((dirs[i] * Math.PI) / 180));
    const v = speeds.map((s, i) => -s * Math.cos((dirs[i] * Math.PI) / 180));
    const header = {
        lo1: WIND_GRID.lonMin,
        la1: WIND_GRID.latMax,
        lo2: WIND_GRID.lonMax,
        la2: WIND_GRID.latMin,
        dx: WIND_GRID.step,
        dy: WIND_GRID.step,
        nx: lons.length,
        ny: lats.length,
        refTime: new Date().toISOString(),
        parameterUnit: 'm.s-1'
    };
    const result = [
        { header: { ...header, parameterCategory: 2, parameterNumber: 2 }, data: u },
        { header: { ...header, parameterCategory: 2, parameterNumber: 3 }, data: v }
    ];
    windGridCache = { at: Date.now(), data: result };
    return result;
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
