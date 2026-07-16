// Спутниковые слои NASA GIBS (без ключей) для ситуационной карты.
// У каждого слоя есть измерение «время»: без аргумента показываем вчера (UTC,
// гарантированно обработано), с датой — архивный срез выбранного сезона.
const BASE = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';
const ATTRIBUTION = 'NASA GIBS / EOSDIS';

function yesterdayUtc() {
    return new Date(Date.now() - 24 * 3600 * 1000).toISOString().slice(0, 10);
}

// VIIRS появился не сразу: NOAA-20 — с января 2018, Suomi NPP — с ноября 2015.
// Для более старых сезонов (паводки с 2010) — MODIS Terra, архив с 2000 года.
function trueColorLayer(date) {
    if (date >= '2018-01-05') return 'VIIRS_NOAA20_CorrectedReflectance_TrueColor';
    if (date >= '2015-11-24') return 'VIIRS_SNPP_CorrectedReflectance_TrueColor';
    return 'MODIS_Terra_CorrectedReflectance_TrueColor';
}

/**
 * @param {string|null} date 'YYYY-MM-DD' — архивный срез (напр. дата выбранного
 *   сезона); null — live-режим «вчера». id стабилен между датами: карта по нему
 *   сохраняет включённость слоя при переключении сезона.
 */
export function gibsOverlays(date = null) {
    const day = date ?? yesterdayUtc();
    const caption = date ? day.split('-').reverse().join('.') : 'вчера';
    return [
        {
            id: 'satellite',
            name: `🛰 Спутниковый снимок (${caption})`,
            url: `${BASE}/${trueColorLayer(day)}/default/${day}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
            opacity: 1,
            maxNativeZoom: 9,
            // непрозрачная подложка — рисуем в базовой тайловой панели, ПОД хороплетом,
            // иначе накрывает всю карту
            pane: 'tilePane',
            attribution: ATTRIBUTION
        },
        {
            id: 'precip',
            name: date ? `🌧 Осадки (IMERG, ${caption})` : '🌧 Осадки (IMERG, последний срез)',
            // слой получасовой: для архива просим полдень UTC — GIBS сам «прищёлкивает»
            // к ближайшему доступному срезу; live-режим — встроенный default (~3–4 ч назад)
            url: `${BASE}/IMERG_Precipitation_Rate/default/${date ? `${day}T12:00:00Z` : 'default'}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`,
            opacity: 0.65,
            maxNativeZoom: 6,
            attribution: ATTRIBUTION
        },
        {
            id: 'snow',
            name: `❄️ Снежный покров (${caption})`,
            url: `${BASE}/MODIS_Terra_NDSI_Snow_Cover/default/${day}/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png`,
            opacity: 0.65,
            maxNativeZoom: 8,
            attribution: ATTRIBUTION
        }
    ];
}
