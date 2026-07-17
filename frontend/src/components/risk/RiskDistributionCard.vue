<script setup>
import { riskBucket } from '@/utils/riskScore';
import { computed } from 'vue';

/**
 * Гистограмма распределения объектов по уровням риска: «сколько НП/районов
 * в какой зоне» — то, что комиссия иначе считает глазами по карте.
 *
 * Бины фиксированные (0–20…80–100), цвета — из единой шкалы utils/riskScore
 * (для 80–100 — более тёмный красный, чтобы отличать от 60–80). Компонент
 * не знает про контур: паводки передают скоры НП, пожары/зима — районов.
 */
const props = defineProps({
    title: { type: String, required: true },
    source: { type: String, default: '' }, // подпись справа: сезон/режим/частота обновления
    values: { type: Object, required: true }, // map id → скор 0–100
    entityLabel: { type: String, default: 'объектов' } // подпись оси Y: «НП» / «районов»
});

const BINS = [
    { label: '0–20', min: 0, max: 20 },
    { label: '20–40', min: 20, max: 40 },
    { label: '40–60', min: 40, max: 60 },
    { label: '60–80', min: 60, max: 80 },
    { label: '80–100', min: 80, max: 101 }
];
// Цвета — из единой шкалы riskBucket по середине бина; 80–100 темнее красного 60–80
const BIN_COLORS = [...BINS.slice(0, 4).map((bin) => riskBucket((bin.min + bin.max) / 2).color), '#7f1d1d'];

const counts = computed(() => {
    const result = BINS.map(() => 0);
    for (const value of Object.values(props.values)) {
        if (typeof value !== 'number') continue;
        const index = BINS.findIndex((bin) => value >= bin.min && value < bin.max);
        if (index !== -1) result[index] += 1;
    }
    return result;
});

const chartData = computed(() => ({
    labels: BINS.map((bin) => bin.label),
    datasets: [{ data: counts.value, backgroundColor: BIN_COLORS, borderRadius: 4 }]
}));

const chartOptions = computed(() => ({
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: props.entityLabel } } },
    maintainAspectRatio: false
}));
</script>

<template>
    <div class="card mb-0 h-full">
        <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
            <h5 class="m-0">{{ title }}</h5>
            <span v-if="source" class="text-muted-color">{{ source }}</span>
        </div>
        <div style="height: 180px">
            <Chart type="bar" :data="chartData" :options="chartOptions" style="height: 100%" />
        </div>
    </div>
</template>
