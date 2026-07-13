<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { api } from '@/service/api';
import { isAdmin } from '@/service/auth';
import { gibsOverlays } from '@/service/gibs';
import { degToCompass, fetchRegionWeather, windMarkers } from '@/service/weather';
import { useToast } from 'primevue/usetoast';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const REGION = 'KZ-SEV'; // СКО — пилотный регион И-6 (см. docs/ideas/i6-flood-risk/plan.md)
const MODULE = 'flood-risk';
const CURRENT_SEASON = '2024';

// Ретроспектива сезонов: модель 2024 на погоде каждого года (см. ml/i6-flood-risk/score_years.py)
const season = ref(CURRENT_SEASON);
const seasonOptions = Array.from({ length: 15 }, (_, i) => String(2024 - i)).map((y) => ({
    label: y === CURRENT_SEASON ? `${y} (актуальный)` : y,
    value: y
}));
const seasonSummary = ref([]);
const base2024Scores = ref({}); // settlementId -> скор 2024 для сравнения в деталке

const toast = useToast();

const loading = ref(true);
const error = ref(null);
const points = ref([]);
const regionValues = ref({});
const selected = ref(null);
const measures = ref([]);
const generating = ref(false);

// Live-погода поверх карты (Open-Meteo): скор — сезонный (снеготаяние),
// live-слой показывает текущую обстановку. Автообновление раз в 15 минут.
const liveWeather = ref(true);
const regionWeather = ref({});
const weatherUpdatedAt = ref(null);
const tileOverlays = gibsOverlays();

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
    } catch {
        weatherUpdatedAt.value = null; // live-слой опционален — страница работает и без него
    }
}

const selectedMeasures = computed(() => (selected.value ? measures.value.filter((m) => m.settlementId === selected.value.id) : []));

// Клик по точке на карте фильтрует очередь мер по выбранному селу
const visibleMeasures = computed(() => (selected.value ? selectedMeasures.value : measures.value));
const scoreBySettlement = computed(() => Object.fromEntries(points.value.map((p) => [p.id, p.value])));

const statusSeverity = { Proposed: 'warn', Approved: 'success', Rejected: 'danger', Done: 'info' };
const statusLabel = { Proposed: 'Предложено', Approved: 'Утверждено', Rejected: 'Отклонено', Done: 'Выполнено' };

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
    const [settlementScores, regionScores, measureList, summary] = await Promise.all([
        api.get(`/settlements/metrics/${MODULE}?metricKey=risk_score&period=${CURRENT_SEASON}`),
        api.get(`/regions/metrics/${MODULE}?metricKey=risk_score`),
        api.get(`/measures/?module=${MODULE}`),
        fetch('/data/season-summary.json').then((r) => (r.ok ? r.json() : []))
    ]);
    points.value = settlementScores.map(toPoint);
    base2024Scores.value = Object.fromEntries(settlementScores.map((s) => [s.settlementId, Math.round(s.value)]));
    regionValues.value = regionScores;
    measures.value = measureList;
    seasonSummary.value = summary;
}

let weatherTimer = null;
onMounted(async () => {
    refreshWeather();
    weatherTimer = setInterval(refreshWeather, 15 * 60 * 1000);
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

const chartData = computed(() => ({
    labels: seasonSummary.value.map((s) => s.year),
    datasets: [
        {
            label: 'Снегозапас марта, % нормы',
            data: seasonSummary.value.map((s) => s.sweMedianPctNorm),
            backgroundColor: seasonSummary.value.map((s) => (String(s.year) === season.value ? '#1d4ed8' : '#93c5fd')),
            borderRadius: 4
        }
    ]
}));
const chartOptions = {
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, title: { display: true, text: '% нормы' } } },
    onClick: (_, elements) => {
        if (elements.length) season.value = String(seasonSummary.value[elements[0].index].year);
    },
    maintainAspectRatio: false
};

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
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
                    <div>
                        <h4 class="m-0">И-6. Паводковый риск-скоринг</h4>
                        <span class="text-muted-color">Риск весеннего затопления населённых пунктов. Пилот: Северо-Казахстанская область.</span>
                    </div>
                    <div class="flex items-center gap-3 flex-wrap">
                        <div class="flex items-center gap-2">
                            <label for="seasonSelect" class="text-muted-color">Сезон</label>
                            <Select v-model="season" inputId="seasonSelect" :options="seasonOptions" optionLabel="label" optionValue="value" size="small" />
                        </div>
                        <div class="flex items-center gap-2">
                            <ToggleSwitch v-model="liveWeather" inputId="liveWeather" />
                            <label for="liveWeather" class="text-muted-color">Live-погода</label>
                            <Tag v-if="liveWeather && weatherUpdatedAt" :value="`обновлено ${weatherUpdatedAt}`" severity="success" />
                        </div>
                        <Tag v-if="points.length" :value="`НП со скорами: ${points.length}`" severity="success" />
                        <Tag v-else value="данные не загружены" severity="warn" />
                        <Button v-if="isAdmin && points.length" label="Сгенерировать черновики мер" icon="pi pi-bolt" size="small" :loading="generating" @click="generateMeasures" />
                    </div>
                </div>
                <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
                <Message v-else-if="!loading && points.length === 0" severity="info" :closable="false">
                    Скоры ещё не загружены. Пайплайн: <code>scripts/download_settlements.py</code> → <code>scripts/load_settlements.py</code> → ML (<code>ml/i6-flood-risk/</code>) → <code>PUT /api/settlements/metrics</code>.
                </Message>
            </div>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <div class="relative">
                    <KazakhstanMap height="72vh" :values="regionValues" :points="points" :markers="weatherMarkers" :tile-overlays="tileOverlays" legend-title="Риск паводка" @point-click="selected = $event" @region-click="selected = null" />

                    <div v-if="!selected" style="position: absolute; top: 1rem; right: 1rem; z-index: 1000">
                        <Tag value="Кликните НП — скор, факторы «почему» и меры" severity="secondary" />
                    </div>
                    <div v-else class="card m-0 shadow-lg" style="position: absolute; top: 1rem; right: 1rem; z-index: 1000; width: 340px; max-width: 85%; max-height: calc(100% - 2rem); overflow-y: auto">
                        <div class="flex items-start justify-between mb-2">
                            <h5 class="m-0">Населённый пункт</h5>
                            <Button icon="pi pi-times" text rounded size="small" @click="selected = null" />
                        </div>
                    <div class="text-2xl font-medium mb-1">{{ selected.name }}</div>
                    <div class="text-muted-color mb-3" v-if="selected.population">Население: {{ selected.population.toLocaleString('ru-RU') }}</div>
                    <div class="mb-4 flex items-center gap-2 flex-wrap">
                        Скор риска ({{ season }}):
                        <Tag :value="selected.value ?? '—'" :severity="selected.value > 60 ? 'danger' : selected.value > 30 ? 'warn' : 'success'" />
                        <Tag v-if="season !== CURRENT_SEASON && base2024Scores[selected.id] !== undefined" :value="`2024: ${base2024Scores[selected.id]}`" severity="secondary" />
                    </div>

                    <h6>Почему такой скор</h6>
                    <ul v-if="selected.factors?.length" class="list-none p-0 m-0 flex flex-col gap-2 mb-4">
                        <li v-for="f in selected.factors" :key="f.name" class="flex items-center justify-between gap-3">
                            <span>{{ f.name }}</span>
                            <Tag :value="(f.impact > 0 ? '+' : '') + f.impact.toFixed(2)" :severity="f.impact > 0 ? 'danger' : 'success'" />
                        </li>
                    </ul>
                    <p v-else class="text-muted-color mb-4">Факторы появятся после загрузки SHAP-объяснений из ML-пайплайна.</p>

                    <h6>Меры по этому НП</h6>
                    <ul v-if="selectedMeasures.length" class="list-none p-0 m-0 flex flex-col gap-2">
                        <li v-for="m in selectedMeasures" :key="m.id" class="flex items-center justify-between gap-2">
                            <span>{{ m.title }}</span>
                            <Tag :value="statusLabel[m.status]" :severity="statusSeverity[m.status]" />
                        </li>
                    </ul>
                        <p v-else-if="selected.value < 20" class="text-muted-color">Риск низкий (скор {{ selected.value }} из 100) — превентивные меры не требуются.</p>
                        <p v-else class="text-muted-color">Мер пока нет — сгенерируйте черновики.</p>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="seasonSummary.length" class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-2">
                    <h5 class="m-0">Снегозапас марта по сезонам, % нормы (клик — переключить сезон)</h5>
                    <span class="text-muted-color">ERA5-Land, медиана по НП региона</span>
                </div>
                <div style="height: 180px">
                    <Chart type="bar" :data="chartData" :options="chartOptions" style="height: 100%" />
                </div>
            </div>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
                    <div class="flex items-center gap-3">
                        <h5 class="m-0">Очередь превентивных мер</h5>
                        <template v-if="selected">
                            <Tag :value="`фильтр: ${selected.name}`" severity="info" />
                            <Button label="Показать все" size="small" text @click="selected = null" />
                        </template>
                    </div>
                    <span class="text-muted-color">Приоритет = скор риска × lg(население); решение принимает комиссия</span>
                </div>
                <DataTable :value="visibleMeasures" paginator :rows="10" size="small" sortField="priority" :sortOrder="-1" :loading="loading">
                    <Column field="settlementName" header="НП" sortable />
                    <Column header="Скор" style="width: 6rem">
                        <template #body="{ data }">
                            <Tag
                                v-if="scoreBySettlement[data.settlementId] !== undefined"
                                :value="scoreBySettlement[data.settlementId]"
                                :severity="scoreBySettlement[data.settlementId] > 60 ? 'danger' : scoreBySettlement[data.settlementId] > 30 ? 'warn' : 'success'"
                            />
                            <span v-else class="text-muted-color">—</span>
                        </template>
                    </Column>
                    <Column field="title" header="Мера" />
                    <Column field="priority" header="Приоритет" sortable style="width: 8rem" />
                    <Column field="status" header="Статус" sortable style="width: 10rem">
                        <template #body="{ data }">
                            <Tag :value="statusLabel[data.status]" :severity="statusSeverity[data.status]" />
                        </template>
                    </Column>
                    <Column field="decidedByName" header="Решение принял" style="width: 12rem">
                        <template #body="{ data }">
                            <span v-if="data.decidedByName">{{ data.decidedByName }}</span>
                            <span v-else class="text-muted-color">—</span>
                        </template>
                    </Column>
                    <Column header="Действия" style="width: 12rem">
                        <template #body="{ data }">
                            <div v-if="data.status === 'Proposed'" class="flex gap-2">
                                <Button label="Утвердить" size="small" severity="success" outlined @click="setStatus(data, 'Approved')" />
                                <Button icon="pi pi-times" size="small" severity="danger" outlined @click="setStatus(data, 'Rejected')" />
                            </div>
                            <Button v-else-if="data.status === 'Approved'" label="Выполнено" size="small" severity="info" outlined @click="setStatus(data, 'Done')" />
                        </template>
                    </Column>
                    <template #empty>
                        <span v-if="selected">По «{{ selected.name }}» мер нет — скор {{ selected.value }} ниже порогов генерации или черновики ещё не создавались.</span>
                        <span v-else>Очередь пуста — загрузите скоры и сгенерируйте черновики мер.</span>
                    </template>
                </DataTable>
            </div>
        </div>
    </div>
</template>
