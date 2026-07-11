<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { ref } from 'vue';

// Демо-скоры паводкового риска (0–100) по регионам — заменить на данные из API,
// когда ML-пайплайн начнёт писать метрики в PostgreSQL (module = 'flood-risk').
const demoScores = ref({
    'KZ-SEV': 87,
    'KZ-AKT': 82,
    'KZ-ZAP': 74,
    'KZ-KUS': 68,
    'KZ-AKM': 61,
    'KZ-PAV': 45,
    'KZ-KAR': 38,
    'KZ-ATY': 33,
    'KZ-VOS': 29,
    'KZ-ALM': 18,
    'KZ-ZHA': 15,
    'KZ-KZY': 12,
    'KZ-YUZ': 10,
    'KZ-MAN': 5
});

const selected = ref(null);
</script>

<template>
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h4 class="m-0">И-6. Паводковый риск-скоринг</h4>
                        <span class="text-muted-color">Риск-карта населённых пунктов к весеннему паводку. Данные: Sentinel-1/2, Copernicus DEM.</span>
                    </div>
                    <Tag value="демо-данные" severity="warn" />
                </div>
            </div>
        </div>

        <div class="col-span-12 lg:col-span-8">
            <div class="card mb-0">
                <KazakhstanMap :values="demoScores" legend-title="Риск паводка" @region-click="selected = $event" />
            </div>
        </div>

        <div class="col-span-12 lg:col-span-4">
            <div class="card mb-0 h-full">
                <h5>Регион</h5>
                <template v-if="selected">
                    <div class="text-2xl font-medium mb-2">{{ selected.name }}</div>
                    <div class="mb-4">
                        Скор риска: <Tag :value="selected.value ?? '—'" :severity="selected.value > 60 ? 'danger' : selected.value > 30 ? 'warn' : 'success'" />
                    </div>
                    <h6>Очередь превентивных мер (заглушка)</h6>
                    <ul class="list-disc pl-6 leading-loose">
                        <li>Обследование дамб и водопропускных сооружений</li>
                        <li>Приоритетная очистка русел</li>
                        <li>План эвакуации для сёл в зоне риска</li>
                    </ul>
                </template>
                <p v-else class="text-muted-color">Кликните регион на карте, чтобы увидеть детали и очередь превентивных мер.</p>
            </div>
        </div>
    </div>
</template>
