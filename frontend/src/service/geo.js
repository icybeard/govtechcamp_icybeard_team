// Районы ADM2: загрузка полигонов и привязка точки к району (ray casting).
// Используется паводковой страницей для агрегации скоров сёл в хороплет районов.

let districtsCache = null;

export async function loadDistricts() {
    if (districtsCache) return districtsCache;
    const geo = await (await fetch('/geo/kz-districts.geojson')).json();
    districtsCache = geo.features.map((f) => {
        const polys = f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates : [f.geometry.coordinates];
        const rings = polys.map((p) => p[0]); // внешних колец достаточно
        let latMin = 90,
            latMax = -90,
            lonMin = 180,
            lonMax = -180;
        for (const ring of rings) {
            for (const [lon, lat] of ring) {
                latMin = Math.min(latMin, lat);
                latMax = Math.max(latMax, lat);
                lonMin = Math.min(lonMin, lon);
                lonMax = Math.max(lonMax, lon);
            }
        }
        return { id: f.properties.shapeID, name: f.properties.shapeName, bbox: [latMin, latMax, lonMin, lonMax], rings };
    });
    return districtsCache;
}

function pointInRing(lat, lon, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i];
        const [xj, yj] = ring[j];
        if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
}

export function findDistrict(lat, lon, districts) {
    for (const d of districts) {
        const [a, b, c, e] = d.bbox;
        if (lat < a || lat > b || lon < c || lon > e) continue;
        if (d.rings.some((ring) => pointInRing(lat, lon, ring))) return d;
    }
    return null;
}
