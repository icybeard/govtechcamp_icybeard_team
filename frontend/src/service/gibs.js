// Спутниковые слои NASA GIBS (без ключей) для ситуационной карты.
// Снимок и снег — за вчера (UTC, гарантированно обработано);
// осадки IMERG отстают на ~3–4 дня, поэтому берём встроенный default-срез GIBS.
const BASE = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';
const ATTRIBUTION = 'NASA GIBS / EOSDIS';

function yesterdayUtc() {
    return new Date(Date.now() - 24 * 3600 * 1000).toISOString().slice(0, 10);
}

export function gibsOverlays() {
    const date = yesterdayUtc();
    return [
        {
            name: '🛰 Спутниковый снимок (вчера)',
            url: `${BASE}/VIIRS_NOAA20_CorrectedReflectance_TrueColor/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
            opacity: 1,
            maxNativeZoom: 9,
            attribution: ATTRIBUTION
        },
        {
            name: '🌧 Осадки (IMERG, последний срез)',
            url: `${BASE}/IMERG_Precipitation_Rate/default/default/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`,
            opacity: 0.65,
            maxNativeZoom: 6,
            attribution: ATTRIBUTION
        },
        {
            name: '❄️ Снежный покров (вчера)',
            url: `${BASE}/MODIS_Terra_NDSI_Snow_Cover/default/${date}/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png`,
            opacity: 0.65,
            maxNativeZoom: 8,
            attribution: ATTRIBUTION
        }
    ];
}
