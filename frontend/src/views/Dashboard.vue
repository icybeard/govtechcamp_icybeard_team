<script setup>
import { api } from '@/service/api';
import { computed, onMounted, ref } from 'vue';

const MODULE = 'flood-risk';

const loading = ref(true);
const error = ref(null);
const scores = ref([]);
const measures = ref([]);

const highRisk = computed(() => scores.value.filter((s) => s.value >= 60));
const populationAtRisk = computed(() => highRisk.value.reduce((sum, s) => sum + (s.population ?? 0), 0));
const top10 = computed(() => [...scores.value].sort((a, b) => b.value - a.value).slice(0, 10));
const measureCounts = computed(() => {
    const counts = { Proposed: 0, Approved: 0, Rejected: 0, Done: 0 };
    for (const m of measures.value) counts[m.status] = (counts[m.status] ?? 0) + 1;
    return counts;
});

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
                        <span class="text-muted-color">Паводковый риск-скоринг (пилот: СКО) + пожарная live-обстановка. AI предлагает — решение принимает человек.</span>
                    </div>
                    <Button label="Открыть карту рисков" icon="pi pi-map" as="router-link" to="/risks/flood" />
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
