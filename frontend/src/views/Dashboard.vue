<script setup>
import { api } from '@/service/api';
import { loadDistricts } from '@/service/geo';
import { computed, onMounted, ref } from 'vue';

const MODULE = 'flood-risk';

const loading = ref(true);
const error = ref(null);
const scores = ref([]);
const measures = ref([]);

// Сводки остальных контуров: статические JSON + кэшированный FIRMS-прокси (без ударов по квотам)
const hotspotsCount = ref(null);
const fireMl = ref(null); // { generatedAt, values }
const winterSeasons = ref({});
const districtNames = ref({}); // shapeID -> имя района

const highRisk = computed(() => scores.value.filter((s) => s.value >= 60));
const populationAtRisk = computed(() => highRisk.value.reduce((sum, s) => sum + (s.population ?? 0), 0));
const top10 = computed(() => [...scores.value].sort((a, b) => b.value - a.value).slice(0, 10));
const measureCounts = computed(() => {
    const counts = { Proposed: 0, Approved: 0, Rejected: 0, Done: 0 };
    for (const m of measures.value) counts[m.status] = (counts[m.status] ?? 0) + 1;
    return counts;
});

function topDistricts(valuesMap, n = 3) {
    return Object.entries(valuesMap)
        .sort((a, b) => b[1] - a[1])
        .slice(0, n)
        .map(([id, value]) => ({ name: districtNames.value[id] ?? id, value: Math.round(value) }));
}

const fireHigh = computed(() => (fireMl.value ? Object.values(fireMl.value.values).filter((v) => v >= 60).length : null));
const fireTop = computed(() => (fireMl.value ? topDistricts(fireMl.value.values) : []));

const winterLatest = computed(() => Object.keys(winterSeasons.value).sort().at(-1));
const winterValues = computed(() => {
    const season = winterSeasons.value[winterLatest.value] ?? {};
    return Object.fromEntries(Object.entries(season).map(([id, d]) => [id, d.risk]));
});
const winterHigh = computed(() => Object.values(winterValues.value).filter((v) => v >= 35).length);
const winterTop = computed(() => topDistricts(winterValues.value));

onMounted(async () => {
    try {
        const [scoreRows, measureRows] = await Promise.all([
            // period обязателен: без него API вернёт все сезоны сразу (520×18 строк)
            api.get(`/settlements/metrics/${MODULE}?metricKey=risk_score&period=2024`),
            api.get(`/measures/?module=${MODULE}`)
        ]);
        scores.value = scoreRows;
        measures.value = measureRows;
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }

    // Не блокируем страницу: сводки контуров подтягиваются независимо и молча деградируют
    loadDistricts()
        .then((list) => (districtNames.value = Object.fromEntries(list.map((d) => [d.id, d.name]))))
        .catch(() => {});
    fetch('/data/fire-ml-today.json')
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => (fireMl.value = j))
        .catch(() => {});
    fetch('/data/winter-districts.json')
        .then((r) => (r.ok ? r.json() : {}))
        .then((j) => (winterSeasons.value = j ?? {}))
        .catch(() => {});
    api.get('/fire/hotspots')
        .then((h) => (hotspotsCount.value = Array.isArray(h) ? h.length : null))
        .catch(() => {});
});

function riskSeverity(value) {
    return value >= 60 ? 'danger' : value >= 30 ? 'warn' : 'success';
}
</script>

<template>
    <div class="grid grid-cols-12 gap-8">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between flex-wrap gap-3">
                    <div>
                        <h4 class="m-0">Превентивное управление природными рисками</h4>
                        <span class="text-muted-color">Паводки (пилот: СКО) · пожары live · зима — по районам. AI предлагает — решение принимает человек.</span>
                    </div>
                    <Button label="Карта паводков" icon="pi pi-map" as="router-link" to="/risks/flood" />
                </div>
                <Message v-if="error" severity="error" :closable="false" class="mt-3">{{ error }}</Message>
            </div>
        </div>

        <!-- Стат-плитки -->
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <span class="block text-muted-color font-medium mb-2">НП со скорами риска</span>
                <div class="text-surface-900 dark:text-surface-0 font-medium text-3xl">{{ loading ? '…' : scores.length }}</div>
                <span class="text-muted-color text-sm">пилотный регион</span>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <span class="block text-muted-color font-medium mb-2">Высокий риск (скор ≥ 60)</span>
                <div class="text-surface-900 dark:text-surface-0 font-medium text-3xl">{{ loading ? '…' : highRisk.length }}</div>
                <span class="text-muted-color text-sm">населённых пунктов</span>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <span class="block text-muted-color font-medium mb-2">Население в зоне риска</span>
                <div class="text-surface-900 dark:text-surface-0 font-medium text-3xl">{{ loading ? '…' : populationAtRisk.toLocaleString('ru-RU') }}</div>
                <span class="text-muted-color text-sm">в НП со скором ≥ 60</span>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <span class="block text-muted-color font-medium mb-2">Мер ждёт решения</span>
                <div class="text-surface-900 dark:text-surface-0 font-medium text-3xl">{{ loading ? '…' : measureCounts.Proposed }}</div>
                <span class="text-muted-color text-sm">утверждено: {{ measureCounts.Approved }}, выполнено: {{ measureCounts.Done }}</span>
            </div>
        </div>

        <!-- Сводки контуров: пожары сегодня и последняя зима -->
        <div class="col-span-12 xl:col-span-6">
            <div class="card mb-0 h-full">
                <div class="flex items-center justify-between mb-3">
                    <h5 class="m-0">🔥 Пожары — сегодня</h5>
                    <Button label="Открыть" size="small" text as="router-link" to="/risks/fire" />
                </div>
                <div class="flex gap-6 mb-3 flex-wrap">
                    <div>
                        <div class="text-2xl font-medium">{{ hotspotsCount ?? '—' }}</div>
                        <span class="text-muted-color text-sm">активных очагов за 24 ч</span>
                    </div>
                    <div>
                        <div class="text-2xl font-medium">{{ fireHigh ?? '—' }}</div>
                        <span class="text-muted-color text-sm">районов с ML-прогнозом ≥ 60</span>
                    </div>
                </div>
                <template v-if="fireTop.length">
                    <span class="text-muted-color text-sm">Топ районов по ML-прогнозу{{ fireMl ? ` (от ${fireMl.generatedAt.slice(11, 16)} UTC)` : '' }}:</span>
                    <ul class="list-none p-0 m-0 mt-2 flex flex-col gap-1">
                        <li v-for="d in fireTop" :key="d.name" class="flex items-center justify-between">
                            <span>{{ d.name }}</span>
                            <Tag :value="d.value" :severity="riskSeverity(d.value)" />
                        </li>
                    </ul>
                </template>
                <p v-else class="text-muted-color text-sm m-0">ML-прогноз не сгенерирован — make fire-today.</p>
            </div>
        </div>

        <div class="col-span-12 xl:col-span-6">
            <div class="card mb-0 h-full">
                <div class="flex items-center justify-between mb-3">
                    <h5 class="m-0">❄️ Зима {{ winterLatest ? `${winterLatest - 1}–${String(winterLatest).slice(2)}` : '' }}</h5>
                    <Button label="Открыть" size="small" text as="router-link" to="/risks/winter" />
                </div>
                <div class="flex gap-6 mb-3 flex-wrap">
                    <div>
                        <div class="text-2xl font-medium">{{ winterLatest ? winterHigh : '—' }}</div>
                        <span class="text-muted-color text-sm">районов с индексом ≥ 35</span>
                    </div>
                </div>
                <template v-if="winterTop.length">
                    <span class="text-muted-color text-sm">Топ районов по индексу зимней опасности:</span>
                    <ul class="list-none p-0 m-0 mt-2 flex flex-col gap-1">
                        <li v-for="d in winterTop" :key="d.name" class="flex items-center justify-between">
                            <span>{{ d.name }}</span>
                            <Tag :value="d.value" :severity="d.value > 60 ? 'danger' : d.value > 35 ? 'warn' : 'success'" />
                        </li>
                    </ul>
                </template>
                <p v-else class="text-muted-color text-sm m-0">Данные зимних сезонов не загружены.</p>
            </div>
        </div>

        <!-- Топ-10 НП по риску -->
        <div class="col-span-12 xl:col-span-7">
            <div class="card mb-0">
                <h5>Топ-10 НП по риску затопления</h5>
                <DataTable :value="top10" size="small" :loading="loading">
                    <Column header="#" style="width: 3rem">
                        <template #body="{ index }">{{ index + 1 }}</template>
                    </Column>
                    <Column field="name" header="Населённый пункт" />
                    <Column field="population" header="Население" style="width: 9rem">
                        <template #body="{ data }">
                            {{ data.population ? data.population.toLocaleString('ru-RU') : '—' }}
                        </template>
                    </Column>
                    <Column field="value" header="Скор" style="width: 7rem">
                        <template #body="{ data }">
                            <Tag :value="Math.round(data.value)" :severity="riskSeverity(data.value)" />
                        </template>
                    </Column>
                    <Column header="Главный фактор">
                        <template #body="{ data }">
                            <span class="text-muted-color">{{ data.factors?.[0]?.name ?? '—' }}</span>
                        </template>
                    </Column>
                    <template #empty>Скоры не загружены — см. пайплайн в ml/i6-flood-risk/README.md</template>
                </DataTable>
            </div>
        </div>

        <!-- Статусы мер -->
        <div class="col-span-12 xl:col-span-5">
            <div class="card mb-0 h-full">
                <h5>Очередь превентивных мер</h5>
                <ul class="list-none p-0 m-0 flex flex-col gap-4 mt-4">
                    <li class="flex items-center justify-between">
                        <span><i class="pi pi-clock text-orange-500 mr-2"></i>Предложено системой</span>
                        <span class="font-medium text-xl">{{ measureCounts.Proposed }}</span>
                    </li>
                    <li class="flex items-center justify-between">
                        <span><i class="pi pi-check-circle text-green-500 mr-2"></i>Утверждено комиссией</span>
                        <span class="font-medium text-xl">{{ measureCounts.Approved }}</span>
                    </li>
                    <li class="flex items-center justify-between">
                        <span><i class="pi pi-times-circle text-red-500 mr-2"></i>Отклонено</span>
                        <span class="font-medium text-xl">{{ measureCounts.Rejected }}</span>
                    </li>
                    <li class="flex items-center justify-between">
                        <span><i class="pi pi-flag-fill text-blue-500 mr-2"></i>Выполнено</span>
                        <span class="font-medium text-xl">{{ measureCounts.Done }}</span>
                    </li>
                </ul>
                <Button label="К очереди мер" icon="pi pi-list" outlined class="w-full mt-6" as="router-link" to="/risks/flood" />
            </div>
        </div>
    </div>
</template>
