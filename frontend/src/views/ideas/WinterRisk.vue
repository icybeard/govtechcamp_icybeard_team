<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import GranularitySwitcher from '@/components/risk/GranularitySwitcher.vue';
import LayersDatePicker from '@/components/risk/LayersDatePicker.vue';
import MapHintBadge from '@/components/risk/MapHintBadge.vue';
import MeasureExplainDialog from '@/components/risk/MeasureExplainDialog.vue';
import MeasuresQueue from '@/components/risk/MeasuresQueue.vue';
import RiskDistributionCard from '@/components/risk/RiskDistributionCard.vue';
import RiskEntityCard from '@/components/risk/RiskEntityCard.vue';
import RiskHeaderCard from '@/components/risk/RiskHeaderCard.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import SeasonalBarChart from '@/components/risk/SeasonalBarChart.vue';
import SeasonPicker from '@/components/risk/SeasonPicker.vue';
import { MEASURE_RULES } from '@/config/measureRules';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { api } from '@/service/api';
import { isAdmin } from '@/service/auth';
import { loadDistricts } from '@/service/geo';
import { gibsOverlays, toIsoDate } from '@/service/gibs';
import { ruDistrictName } from '@/utils/districtNames';
import { riskSeverity } from '@/utils/riskScore';
import { useToast } from 'primevue/usetoast';
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

// Зимняя обстановка ПО РАЙОНАМ (ADM2, 174). Данные готовит scripts/winter_fetch_districts.py
// (один раз) в frontend/public/data/winter-districts.json — страница читает статический файл,
// БД не участвует. Индекс 0–100 = 0.30·гололёд + 0.30·метель + 0.20·снегонагрузка + 0.20·холод.
const GEO_URL = '/geo/kz-districts.geojson';
const CURRENT = '2026'; // последняя завершённая зима 2025–26
const BLUE = ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'];
const HAZARD = RISK_HAZARDS.winter;

// Скоринг зимы есть только на уровне района — «Населённый пункт»
// в GranularitySwitcher заблокирован (как в макете), пока нет модели по НП.
const GRANULARITY = 'region';

const SUBS = [
    { key: 'glaze', label: 'Гололёд' },
    { key: 'blizzard', label: 'Метель/заносы' },
    { key: 'snowload', label: 'Снеговая нагрузка' },
    { key: 'cold', label: 'Холод' }
];

const season = ref(CURRENT);
// Метка сплита ML — как «2024 (паводок — обучение модели)» у паводков:
// модель обучена на зимах до 2024–25, последняя зима — честный тест
const HISTORY_OPTIONS = Array.from({ length: 7 }, (_, i) => String(2026 - i)).map((y) => ({
    label: y === CURRENT ? `зима ${+y - 1}–${y.slice(2)} (последняя — тест ML)` : `зима ${+y - 1}–${y.slice(2)}`,
    value: y
}));

// Слои GIBS следуют дате в пикере. Дефолт от сезона: середина февраля года Y —
// разгар зимы (Y-1)–Y; смена сезона сбрасывает дату на его дефолт.
const layerDate = ref(new Date(+season.value, 1, 15));
watch(season, (y) => (layerDate.value = new Date(+y, 1, 15)));
const tileOverlays = computed(() => gibsOverlays(toIsoDate(layerDate.value)));

const route = useRoute();
const loading = ref(true);
const error = ref(null);
const allSeasons = ref({}); // { '2026': { shapeID: {risk, glaze, ...} } }
const selected = ref(null);

// ML-ретроспектива как у паводков (ml/i-winter-risk/winter_ml.py seasons):
// { '2026': { shapeID: { score, proba, factors: [{name, impact}] } } },
// где score — ранг района внутри сезона 0–100 (для карты), proba — средняя
// вероятность опасного дня в % (показывается в карточке).
// Файла нет — режим «ML-прогноз» задизейблен, работает формульный индекс.
const mlSeasons = ref(null);
// ML-прогноз на сегодня (winter_ml.py today / make winter-today) — псевдосезон
// «сегодня» в пикере: { generatedAt, values: {id: score}, factors: {id: [...]} }
const mlToday = ref(null);
const mode = ref('index');
const modeOptions = computed(() => [
    { label: 'Индекс', value: 'index' },
    { label: 'ML-прогноз', value: 'ml', disabled: !mlSeasons.value }
]);

// Пункт «сегодня» — только в зимний сезон (ноябрь–март): модель обучена на этих
// месяцах, летний прогноз — экстраполяция вне области применимости (см. winter_ml.py)
const WINTER_NOW = [11, 12, 1, 2, 3].includes(new Date().getMonth() + 1);
const isToday = computed(() => season.value === 'today');
const seasonOptions = computed(() => [
    ...(mlToday.value && WINTER_NOW ? [{ label: `сегодня (ML-прогноз от ${mlToday.value.generatedAt.slice(11, 16)} UTC)`, value: 'today' }] : []),
    ...HISTORY_OPTIONS
]);

const seasonData = computed(() => allSeasons.value[season.value] ?? {});
const mlSeason = computed(() => mlSeasons.value?.[season.value] ?? null);
// «Сегодня» существует только в ML-виде: формульный индекс считается по архиву за весь сезон
const isMl = computed(() => isToday.value || (mode.value === 'ml' && mlSeason.value !== null));

const indexValues = computed(() => Object.fromEntries(Object.entries(seasonData.value).map(([id, d]) => [id, d.risk])));
const mapValues = computed(() => {
    if (isToday.value) return mlToday.value?.values ?? {};
    if (isMl.value) return Object.fromEntries(Object.entries(mlSeason.value).map(([id, d]) => [id, d.score]));
    return indexValues.value;
});
const legendTitle = computed(() => (isToday.value ? 'Зимний риск (ML, сегодня)' : isMl.value ? 'Зимний риск (ML)' : 'Зимний риск'));
const hasData = computed(() => Object.keys(mapValues.value).length > 0);

// Сезонный график — аналог «снегозапаса» у паводков: средний индекс по всем
// районам за каждую зиму, клик по столбцу переключает сезон вверху страницы
const chartLabel = (y) => `${+y - 1}–${y.slice(2)}`;
const seasonChart = computed(() =>
    Object.keys(allSeasons.value)
        .sort()
        .map((y) => {
            const risks = Object.values(allSeasons.value[y]).map((d) => d.risk);
            const mean = risks.length ? risks.reduce((sum, v) => sum + v, 0) / risks.length : 0;
            return { label: chartLabel(y), value: y, mean: Math.round(mean * 10) / 10 };
        })
);

function selectChartSeason(label) {
    const entry = seasonChart.value.find((s) => s.label === label);
    if (entry) season.value = entry.value;
}

onMounted(async () => {
    loadMeasures();
    loadDistricts()
        .then((list) => (districtNames.value = Object.fromEntries(list.map((d) => [d.id, ruDistrictName(d.name)]))))
        .catch(() => {});
    try {
        const response = await fetch('/data/winter-districts.json');
        if (!response.ok) throw new Error('winter-districts.json не найден');
        allSeasons.value = await response.json();
        // Deep-link с дашборда: ?district=<shapeID> — открыть карточку района
        const districtId = route.query.district;
        if (districtId && seasonData.value[districtId]) {
            onRegionClick({ iso: String(districtId), name: districtNames.value[districtId] ?? String(districtId) });
        }
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }
    try {
        const response = await fetch('/data/winter-ml-seasons.json');
        if (response.ok) mlSeasons.value = await response.json();
    } catch {
        /* ML-ретроспектива опциональна — селектор режима задизейблен */
    }
    try {
        const response = await fetch('/data/winter-ml-today.json');
        if (response.ok) mlToday.value = await response.json();
    } catch {
        /* прогноз на сегодня опционален — пункт «сегодня» не показывается */
    }
});

function onRegionClick(region) {
    const d = seasonData.value[region.iso];
    const ml = isToday.value
        ? (mlToday.value?.values?.[region.iso] !== undefined ? { score: mlToday.value.values[region.iso], factors: mlToday.value.factors?.[region.iso] ?? [] } : null)
        : (mlSeason.value?.[region.iso] ?? null);
    if (!d && !ml) {
        selected.value = null;
        return;
    }
    // История района по всем зимам (аналог блока «История» у пожаров):
    // средний индекс + самая суровая зима — контекст «как здесь обычно»
    const perSeason = Object.entries(allSeasons.value)
        .filter(([, districts]) => districts[region.iso] !== undefined)
        .map(([year, districts]) => ({ year, risk: Math.round(districts[region.iso].risk) }));
    const history = perSeason.length
        ? { count: perSeason.length, mean: Math.round(perSeason.reduce((sum, s) => sum + s.risk, 0) / perSeason.length), worst: perSeason.reduce((a, b) => (b.risk > a.risk ? b : a)) }
        : null;

    selected.value = {
        iso: region.iso,
        name: region.name,
        value: d ? Math.round(d.risk) : null,
        parts: d ? SUBS.map((s) => ({ label: s.label, value: Math.round(d[s.key] ?? 0) })) : [],
        ml,
        history
    };
}

// ── Очередь превентивных мер по районам ─────────────────────────────────────
// Скоры для генерации — risk выбранного сезона из статического JSON: районов
// в БД нет, фронт шлёт districtValues (shapeID → скор+имя) в /measures/generate.
const toast = useToast();
const measures = ref([]);
const generating = ref(false);
const districtNames = ref({}); // shapeID -> имя района (geojson)

// очередь переиспользует колонки НП: district-поля мапим в settlement-поля
const queueRows = computed(() => measures.value.map((m) => ({ ...m, settlementId: m.districtId, settlementName: m.districtName })));
const visibleMeasures = computed(() => (selected.value?.iso ? queueRows.value.filter((m) => m.settlementId === selected.value.iso) : queueRows.value));

async function loadMeasures() {
    try {
        measures.value = await api.get('/measures/?module=winter-risk');
    } catch {
        measures.value = [];
    }
}

async function generateMeasures() {
    generating.value = true;
    try {
        // Меры генерируются по формульному индексу выбранного сезона (не по ML-рангу)
        const districtValues = Object.fromEntries(
            Object.entries(indexValues.value)
                .filter(([id]) => districtNames.value[id])
                .map(([id, value]) => [id, { value, name: districtNames.value[id] }])
        );
        const result = await api.post('/measures/generate', { module: 'winter-risk', metricKey: 'risk_score', period: season.value, districtValues });
        toast.add({ severity: 'success', summary: `Создано черновиков: ${result.created}`, life: 4000 });
        await loadMeasures();
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

// Объяснимость: правило + субиндексы зимы (гололёд/метель/снегонагрузка/холод)
const explainMeasure = ref(null);
const explainVisible = ref(false);
const explainScore = computed(() => {
    const v = indexValues.value[explainMeasure.value?.settlementId];
    return v === undefined ? null : Math.round(v);
});
const explainFactors = computed(() => {
    const d = seasonData.value[explainMeasure.value?.settlementId];
    if (!d) return [];
    return SUBS.map((s) => {
        const v = Math.round(d[s.key] ?? 0);
        return { name: s.label, display: String(v), severity: riskSeverity(v) };
    });
});
function openExplain(measure) {
    explainMeasure.value = measure;
    explainVisible.value = true;
}
</script>

<template>
    <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12">
            <RiskHeaderCard title="Зимний риск-скоринг" description="174 района, сезоны 2019–20…2025–26, ERA5-архив. Режимы: «Индекс» — прозрачная формула (гололёд + метель + снегонагрузка + холод), «ML-прогноз» — LightGBM на предупреждениях Казгидромета (обучение — до зимы 2024–25, последняя зима — тест).">
                <template #controls>
                    <SeasonPicker v-model="season" :options="seasonOptions" />
                    <SelectButton v-model="mode" :options="modeOptions" optionLabel="label" optionValue="value" optionDisabled="disabled" size="small" :disabled="isToday" :title="isToday ? 'Для «сегодня» доступен только ML-прогноз' : ''" />
                    <LayersDatePicker v-model="layerDate" />

                    <Tag v-if="loading" value="загрузка…" severity="secondary" />
                    <Tag v-else-if="hasData" :value="`Районов со скорами: ${Object.keys(mapValues).length}`" severity="success" />
                    <Tag v-else value="данные не загружены" severity="warn" />

                </template>
                <template #actions>
                    <GranularitySwitcher :model-value="GRANULARITY" :supports-region="true" :supports-np="false" />
                </template>
                <template #messages>
                    <Message v-if="error" severity="error" :closable="false" class="mt-4">{{ error }}</Message>
                    <Message v-else-if="!loading && !hasData" severity="info" :closable="false" class="mt-4">
                        Данные не сгенерированы: <code>python3 scripts/winter_fetch_districts.py</code> (один раз, ~3 минуты) — файл попадёт в сборку фронтенда.
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
                    <KazakhstanMap height="600px" :geo-url="GEO_URL" :values="mapValues" :palette="BLUE" :domain-min="0" :domain-max="100" :tile-overlays="tileOverlays" :legend-title="legendTitle" :selected-id="selected?.iso ?? null" :format-name="ruDistrictName" @region-click="onRegionClick" />

                    <MapHintBadge v-if="!selected" text="Кликните район — скор, факторы «почему» и меры" />
                    <RiskEntityCard v-else entity-label="Район" :name="selected.name" :color="HAZARD.color" @close="selected = null">
                        <!-- Режим ML — скор модели и SHAP-факторы «почему», как у паводков -->
                        <template v-if="isMl && selected.ml">
                            <div class="risk-meta-row" :class="selected.ml.proba !== undefined ? 'mb-2' : 'mb-4'">
                                Риск района ({{ seasonOptions.find((o) => o.value === season)?.label }}):
                                <RiskScoreBadge :score="selected.ml.score" />
                            </div>
                            <div v-if="selected.ml.proba !== undefined" class="risk-meta-row mb-4">Вероятность опасного дня (в среднем за сезон): {{ selected.ml.proba }}%</div>

                            <div class="risk-section-title">Почему такой скор</div>
                            <ul v-if="selected.ml.factors?.length" class="list-none p-0 m-0 flex flex-col gap-2 mb-3">
                                <li v-for="f in selected.ml.factors" :key="f.name" class="risk-metric-row">
                                    <span class="risk-metric-label">{{ f.name }}</span>
                                    <Tag :value="(f.impact > 0 ? '+' : '') + f.impact.toFixed(2)" :severity="f.impact > 0 ? 'danger' : 'success'" />
                                </li>
                            </ul>
                            <p class="risk-footnote mb-0">LightGBM на предупреждениях Казгидромета (метель/гололёд/мороз); скор — {{ isToday ? 'вероятность опасного дня сегодня' : 'ранг района среди 174 районов сезона по вероятности опасных дней' }}.</p>
                        </template>

                        <!-- Режим формульного индекса — разбор по компонентам -->
                        <template v-else>
                            <div class="risk-meta-row mb-4">
                                Риск района ({{ seasonOptions.find((o) => o.value === season)?.label }}):
                                <RiskScoreBadge :score="selected.value" />
                            </div>

                            <div class="risk-section-title">Из чего складывается (0–100 по каждому)</div>
                            <ul class="list-none p-0 m-0 flex flex-col gap-2 mb-3">
                                <li v-for="p in selected.parts" :key="p.label" class="risk-metric-row">
                                    <span class="risk-metric-label">{{ p.label }}</span>
                                    <Tag :value="p.value" :severity="riskSeverity(p.value)" />
                                </li>
                            </ul>
                            <p class="risk-footnote mb-0">Итог — взвешенный композит: гололёд 0.30 + метель 0.30 + снегонагрузка 0.20 + холод 0.20.</p>
                        </template>

                        <template v-if="selected.history">
                            <div class="risk-section-title" style="margin-top: 12px">История ({{ selected.history.count }} зим)</div>
                            <div class="risk-metric-row mb-2">
                                <span class="risk-metric-label">Средний индекс района</span>
                                <Tag :value="selected.history.mean" :severity="riskSeverity(selected.history.mean)" />
                            </div>
                            <p class="risk-footnote mb-0">Самая суровая: зима {{ +selected.history.worst.year - 1 }}–{{ selected.history.worst.year.slice(2) }} (индекс {{ selected.history.worst.risk }}).</p>
                        </template>
                    </RiskEntityCard>
                </div>
            </div>
        </div>

        <div v-if="!isToday && seasonChart.length" class="col-span-12 xl:col-span-8">
            <SeasonalBarChart
                title="Индекс зимней опасности по сезонам, средний по районам (клик — переключить сезон)"
                source="ERA5-Land, по районам"
                :labels="seasonChart.map((s) => s.label)"
                :values="seasonChart.map((s) => s.mean)"
                :active-label="chartLabel(season)"
                :color="HAZARD.color"
                y-title="индекс 0–100"
                @select="selectChartSeason"
            />
        </div>

        <div v-if="hasData" class="col-span-12" :class="{ 'xl:col-span-4': !isToday && seasonChart.length }">
            <RiskDistributionCard title="Распределение районов по уровню риска" :source="isMl ? 'ML' : 'индекс'" :values="mapValues" entity-label="районов" />
        </div>

        <div class="col-span-12">
            <MeasuresQueue :measures="visibleMeasures" entity-label="Район" :scores="indexValues" can-decide priority-hint="Приоритет = скор риска района; решение принимает комиссия" @set-status="setStatus" @explain="openExplain">
                <template #filter>
                    <Button v-if="isAdmin" label="Сгенерировать черновики мер" icon="pi pi-bolt" :loading="generating" :disabled="!hasData" @click="generateMeasures" />
                    <template v-if="selected?.iso">
                        <Tag :value="`фильтр: ${selected.name}`" severity="info" />
                        <Button label="Показать все" size="small" text @click="selected = null" />
                    </template>
                </template>
                <template #empty>
                    <span v-if="selected?.iso">По району «{{ selected.name }}» мер нет — скор ниже порогов или черновики ещё не создавались.</span>
                    <span v-else>Очередь пуста — сгенерируйте черновики по скорам выбранного сезона.</span>
                </template>
            </MeasuresQueue>
        </div>

        <MeasureExplainDialog v-model:visible="explainVisible" :measure="explainMeasure" entity-label="Район" :score="explainScore" :factors="explainFactors" :rules="MEASURE_RULES['winter-risk']" priority-note="скор риска района за сезон генерации (население района не учитывается)" />
    </div>
</template>
