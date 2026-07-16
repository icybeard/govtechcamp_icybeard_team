<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import GranularitySwitcher from '@/components/risk/GranularitySwitcher.vue';
import MapHintBadge from '@/components/risk/MapHintBadge.vue';
import MeasuresQueue from '@/components/risk/MeasuresQueue.vue';
import RiskEntityCard from '@/components/risk/RiskEntityCard.vue';
import RiskHeaderCard from '@/components/risk/RiskHeaderCard.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import SeasonalBarChart from '@/components/risk/SeasonalBarChart.vue';
import SeasonPicker from '@/components/risk/SeasonPicker.vue';
import { MEASURE_STATUS } from '@/config/measureStatus';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { api } from '@/service/api';
import { isAdmin } from '@/service/auth';
import { findDistrict, loadDistricts } from '@/service/geo';
import LayersDatePicker from '@/components/risk/LayersDatePicker.vue';
import { gibsOverlays, toIsoDate } from '@/service/gibs';
import { degToCompass, fetchRegionWeather, fetchWindGrid, windMarkers } from '@/service/weather';
import { useToast } from 'primevue/usetoast';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const MODULE = 'flood-risk';
const CURRENT_SEASON = '2024';
const HAZARD = RISK_HAZARDS.flood;

// Скоринг паводков есть только на уровне НП — «Регион» в GranularitySwitcher
// заблокирован (как в макете), пока модель не научится агрегировать риск на район.
const GRANULARITY = 'np';

// Ретроспектива сезонов: модель 2024 на погоде каждого года (см. ml/i6-flood-risk/score_years.py)
const season = ref(CURRENT_SEASON);
const seasonOptions = Array.from({ length: 17 }, (_, i) => String(2026 - i)).map((y) => ({
    label: y === CURRENT_SEASON ? `${y} (паводок — обучение модели)` : y,
    value: y
}));
const seasonSummary = ref([]);
const base2024Scores = ref({}); // settlementId -> скор 2024 для сравнения в деталке

const toast = useToast();

const loading = ref(true);
const error = ref(null);
const points = ref([]);
const selected = ref(null);
const measures = ref([]);
const generating = ref(false);

// Хороплет районов: скор района = максимум по его сёлам — контекстная подложка
// под точками НП. Привязка село→район считается один раз (point-in-polygon),
// сезоны меняют только значения. Скоринг при этом остаётся на уровне НП —
// «Регион» в переключателе детализации заблокирован.
const GEO_URL = '/geo/kz-districts.geojson';
const districtBySettlement = ref({}); // settlementId -> shapeID
const districtValues = computed(() => {
    const acc = {};
    for (const p of points.value) {
        const districtId = districtBySettlement.value[p.id];
        if (!districtId) continue;
        acc[districtId] = Math.max(acc[districtId] ?? 0, p.value);
    }
    return acc;
});

async function assignDistricts() {
    const districts = await loadDistricts();
    const assignments = {};
    for (const p of points.value) {
        assignments[p.id] = findDistrict(p.lat, p.lon, districts)?.id ?? null;
    }
    districtBySettlement.value = assignments;
}

// Live-погода поверх карты (Open-Meteo): скор — сезонный (снеготаяние),
// live-слой показывает текущую обстановку. Автообновление раз в час.
const liveWeather = ref(true);
const regionWeather = ref({});
const weatherUpdatedAt = ref(null);
const windGrid = ref(null);
// Слои GIBS следуют дате в пикере. Дефолт от сезона: середина марта — максимум
// снегозапаса перед таянием; смена сезона сбрасывает дату на его дефолт.
const layerDate = ref(new Date(+season.value, 2, 15));
watch(season, (y) => (layerDate.value = new Date(+y, 2, 15)));
const tileOverlays = computed(() => gibsOverlays(toIsoDate(layerDate.value)));

const weatherMarkers = computed(() =>
    liveWeather.value
        ? windMarkers(
              regionWeather.value,
              (w) => `${w.name}: ветер ${w.windSpeed} км/ч ${degToCompass(w.windDir)} · осадки 24ч ${w.precip24h} мм · прогноз ${w.forecast24h} мм · ${w.temp} °C`
          )
        : []
);

async function refreshWeather() {
    try {
        const { updatedAt, regions } = await fetchRegionWeather();
        regionWeather.value = regions;
        weatherUpdatedAt.value = updatedAt;
        windGrid.value = await fetchWindGrid(); // анимация частиц ветра
    } catch {
        weatherUpdatedAt.value = null; // live-слой опционален — страница работает и без него
    }
}

const selectedMeasures = computed(() => (selected.value ? measures.value.filter((m) => m.settlementId === selected.value.id) : []));

// Клик по точке на карте фильтрует очередь мер по выбранному селу
const visibleMeasures = computed(() => (selected.value ? selectedMeasures.value : measures.value));
const scoreBySettlement = computed(() => Object.fromEntries(points.value.map((p) => [p.id, p.value])));

function toPoint(s) {
    return {
        id: s.settlementId,
        name: s.name,
        lat: s.lat,
        lon: s.lon,
        value: Math.round(s.value),
        population: s.population,
        factors: s.factors
    };
}

async function loadSeasonScores() {
    const rows = await api.get(`/settlements/metrics/${MODULE}?metricKey=risk_score&period=${season.value}`);
    points.value = rows.map(toPoint);
    selected.value = null;
}

async function loadAll() {
    const [settlementScores, measureList, summary] = await Promise.all([
        api.get(`/settlements/metrics/${MODULE}?metricKey=risk_score&period=${CURRENT_SEASON}`),
        api.get(`/measures/?module=${MODULE}`),
        fetch('/data/season-summary.json').then((r) => (r.ok ? r.json() : []))
    ]);
    points.value = settlementScores.map(toPoint);
    base2024Scores.value = Object.fromEntries(settlementScores.map((s) => [s.settlementId, Math.round(s.value)]));
    measures.value = measureList;
    seasonSummary.value = summary;
    await assignDistricts();
}

let weatherTimer = null;
onMounted(async () => {
    refreshWeather();
    weatherTimer = setInterval(refreshWeather, 60 * 60 * 1000); // раз в час — бережём лимит Open-Meteo
    try {
        await loadAll();
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }
});
onBeforeUnmount(() => clearInterval(weatherTimer));

watch(season, loadSeasonScores);

async function generateMeasures() {
    generating.value = true;
    try {
        const result = await api.post('/measures/generate', { module: MODULE, metricKey: 'risk_score', period: null });
        toast.add({ severity: 'success', summary: `Создано черновиков: ${result.created}`, life: 4000 });
        measures.value = await api.get(`/measures/?module=${MODULE}`);
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Ошибка генерации', detail: e.message, life: 5000 });
    } finally {
        generating.value = false;
    }
}

async function setStatus(measure, status) {
    try {
        const updated = await api.put(`/measures/${measure.id}/status`, { status, note: null });
        measures.value = measures.value.map((m) => (m.id === updated.id ? updated : m));
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Не удалось изменить статус', detail: e.message, life: 5000 });
    }
}
</script>

<template>
    <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12">
            <RiskHeaderCard title="Паводковый риск-скоринг" description="Риск весеннего затопления населённых пунктов (ML-модель на событии 2024). Пилот: Северо-Казахстанская область.">
                <template #controls>
                    <SeasonPicker v-model="season" :options="seasonOptions" />
                    <LayersDatePicker v-model="layerDate" />

                    <div class="flex items-center gap-2">
                        <ToggleSwitch v-model="liveWeather" inputId="liveWeather" />
                        <label for="liveWeather" class="text-muted-color">Live-погода</label>
                    </div>

                    <Tag v-if="liveWeather && weatherUpdatedAt" :value="`обновлено ${weatherUpdatedAt}`" severity="success" />
                    <Tag v-if="points.length" :value="`НП со скорами: ${points.length}`" severity="success" />
                    <Tag v-else value="данные не загружены" severity="warn" />

                    <div class="flex items-center gap-3 flex-wrap" style="margin-left: auto">
                        <GranularitySwitcher :model-value="GRANULARITY" :supports-region="false" :supports-np="true" />
                        <Button v-if="isAdmin && points.length" label="Сгенерировать черновики мер" severity="contrast" size="small" :loading="generating" @click="generateMeasures" />
                    </div>
                </template>
                <template #messages>
                    <Message v-if="error" severity="error" :closable="false" class="mt-4">{{ error }}</Message>
                    <Message v-else-if="!loading && points.length === 0" severity="info" :closable="false" class="mt-4">
                        Скоры ещё не загружены. Пайплайн: <code>scripts/download_settlements.py</code> → <code>scripts/load_settlements.py</code> → ML (<code>ml/i6-flood-risk/</code>) → <code>PUT /api/settlements/metrics</code>.
                    </Message>
                </template>
            </RiskHeaderCard>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <!-- isolate: свой контекст наложения — карточка объекта и подсказка (z-index 1000)
                     не всплывают над фиксированным топбаром при прокрутке -->
                <div class="relative isolate">
                    <!-- 600px — высота основной карты по дизайн-спецификации -->
                    <KazakhstanMap height="600px" :geo-url="GEO_URL" :values="districtValues" :points="points" :markers="weatherMarkers" :tile-overlays="tileOverlays" :wind-grid="liveWeather ? windGrid : null" legend-title="Риск паводка" @point-click="selected = $event" @region-click="selected = null" />

                    <MapHintBadge v-if="!selected" text="Кликните НП — скор, факторы «почему» и меры" />
                    <RiskEntityCard v-else entity-label="Населённый пункт" :name="selected.name" :color="HAZARD.color" @close="selected = null">
                        <div v-if="selected.population" class="risk-meta-row mb-3">Население: {{ selected.population.toLocaleString('ru-RU') }}</div>
                        <div class="risk-meta-row mb-4">
                            Риск НП ({{ season }}):
                            <RiskScoreBadge :score="selected.value" />
                            <Tag v-if="season !== CURRENT_SEASON && base2024Scores[selected.id] !== undefined" :value="`2024: ${base2024Scores[selected.id]}`" severity="secondary" />
                        </div>

                        <div class="risk-section-title">Почему такой скор</div>
                        <ul v-if="selected.factors?.length" class="list-none p-0 m-0 flex flex-col gap-2 mb-4">
                            <li v-for="f in selected.factors" :key="f.name" class="risk-metric-row">
                                <span class="risk-metric-label">{{ f.name }}</span>
                                <Tag :value="(f.impact > 0 ? '+' : '') + f.impact.toFixed(2)" :severity="f.impact > 0 ? 'danger' : 'success'" />
                            </li>
                        </ul>
                        <p v-else class="text-muted-color mb-4">Факторы появятся после загрузки SHAP-объяснений из ML-пайплайна.</p>

                        <div class="risk-section-title">Меры по этому НП</div>
                        <ul v-if="selectedMeasures.length" class="list-none p-0 m-0 flex flex-col gap-2">
                            <li v-for="m in selectedMeasures" :key="m.id" class="risk-metric-row">
                                <span class="risk-metric-label">{{ m.title }}</span>
                                <Tag :value="MEASURE_STATUS[m.status]?.label ?? m.status" :severity="MEASURE_STATUS[m.status]?.severity ?? 'secondary'" />
                            </li>
                        </ul>
                        <p v-else-if="selected.value < 20" class="text-muted-color">Риск низкий (скор {{ selected.value }} из 100) — превентивные меры не требуются.</p>
                        <p v-else class="text-muted-color">Мер пока нет — сгенерируйте черновики.</p>
                    </RiskEntityCard>
                </div>
            </div>
        </div>

        <div v-if="seasonSummary.length" class="col-span-12">
            <SeasonalBarChart
                title="Снегозапас марта по сезонам, % нормы (клик — переключить сезон)"
                source="ERA5-Land, медиана по НП региона"
                :labels="seasonSummary.map((s) => String(s.year))"
                :values="seasonSummary.map((s) => s.sweMedianPctNorm)"
                :active-label="season"
                :color="HAZARD.color"
                y-title="% нормы"
                @select="season = $event"
            />
        </div>

        <div class="col-span-12">
            <MeasuresQueue :measures="visibleMeasures" :loading="loading" entity-label="НП" :scores="scoreBySettlement" can-decide @set-status="setStatus">
                <template #filter>
                    <template v-if="selected">
                        <Tag :value="`фильтр: ${selected.name}`" severity="info" />
                        <Button label="Показать все" size="small" text @click="selected = null" />
                    </template>
                </template>
                <template #empty>
                    <span v-if="selected">По «{{ selected.name }}» мер нет — скор {{ selected.value }} ниже порогов генерации или черновики ещё не создавались.</span>
                    <span v-else>Очередь пуста — загрузите скоры и сгенерируйте черновики мер.</span>
                </template>
            </MeasuresQueue>
        </div>
    </div>
</template>
