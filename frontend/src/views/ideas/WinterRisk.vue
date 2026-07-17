<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import GranularitySwitcher from '@/components/risk/GranularitySwitcher.vue';
import MapHintBadge from '@/components/risk/MapHintBadge.vue';
import RiskEntityCard from '@/components/risk/RiskEntityCard.vue';
import RiskHeaderCard from '@/components/risk/RiskHeaderCard.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import SeasonPicker from '@/components/risk/SeasonPicker.vue';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { gibsOverlays } from '@/service/gibs';
import { riskSeverity } from '@/utils/riskScore';
import { computed, onMounted, ref } from 'vue';

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

const tileOverlays = gibsOverlays(); // снежный покров/снимок — те же слои GIBS

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

onMounted(async () => {
    try {
        const response = await fetch('/data/winter-districts.json');
        if (!response.ok) throw new Error('winter-districts.json не найден');
        allSeasons.value = await response.json();
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
        name: region.name,
        value: d ? Math.round(d.risk) : null,
        parts: d ? SUBS.map((s) => ({ label: s.label, value: Math.round(d[s.key] ?? 0) })) : [],
        ml,
        history
    };
}
</script>

<template>
    <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12">
            <RiskHeaderCard title="Зимний риск-скоринг" description="174 района, сезоны 2019–20…2025–26, ERA5-архив. Режимы: «Индекс» — прозрачная формула (гололёд + метель + снегонагрузка + холод), «ML-прогноз» — LightGBM на предупреждениях Казгидромета (обучение — до зимы 2024–25, последняя зима — тест).">
                <template #controls>
                    <SeasonPicker v-model="season" :options="seasonOptions" />
                    <SelectButton v-model="mode" :options="modeOptions" optionLabel="label" optionValue="value" optionDisabled="disabled" size="small" :disabled="isToday" :title="isToday ? 'Для «сегодня» доступен только ML-прогноз' : ''" />

                    <Tag v-if="loading" value="загрузка…" severity="secondary" />
                    <Tag v-else-if="hasData" :value="`Районов со скорами: ${Object.keys(mapValues).length}`" severity="success" />
                    <Tag v-else value="данные не загружены" severity="warn" />

                    <div style="margin-left: auto">
                        <GranularitySwitcher :model-value="GRANULARITY" :supports-region="true" :supports-np="false" />
                    </div>
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
                    <KazakhstanMap height="600px" :geo-url="GEO_URL" :values="mapValues" :palette="BLUE" :domain-min="0" :domain-max="100" :tile-overlays="tileOverlays" :legend-title="legendTitle" @region-click="onRegionClick" />

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
    </div>
</template>
