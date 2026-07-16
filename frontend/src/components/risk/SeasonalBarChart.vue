<script setup>
import { computed } from 'vue';

/**
 * Карточка сезонного графика — по макету: заголовок слева, источник данных
 * справа, столбики по сезонам. Активный сезон подсвечен цветом контура,
 * клик по столбику переключает сезон (emit 'select' со значением подписи).
 *
 * Компонент не знает про метрику — паводки передают снегозапас, зима —
 * индекс опасности; новый контур подключается одними пропсами.
 */
const props = defineProps({
    title: { type: String, required: true },
    source: { type: String, default: '' },
    labels: { type: Array, required: true }, // подписи сезонов, напр. ['2010', '2011', ...]
    values: { type: Array, required: true }, // значения той же длины
    activeLabel: { type: String, default: null }, // подпись подсвеченного сезона
    color: { type: String, required: true }, // акцент контура (RISK_HAZARDS[*].color)
    inactiveColor: { type: String, default: '#93c5fd' },
    yTitle: { type: String, default: '' }
});
const emit = defineEmits(['select']);

const chartData = computed(() => ({
    labels: props.labels,
    datasets: [
        {
            data: props.values,
            backgroundColor: props.labels.map((label) => (label === props.activeLabel ? props.color : props.inactiveColor)),
            borderRadius: 4
        }
    ]
}));

const chartOptions = computed(() => ({
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, title: { display: Boolean(props.yTitle), text: props.yTitle } } },
    onClick: (_, elements) => {
        if (elements.length) emit('select', props.labels[elements[0].index]);
    },
    maintainAspectRatio: false
}));
</script>

<template>
    <div class="card mb-0">
        <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
            <h5 class="m-0">{{ title }}</h5>
            <span v-if="source" class="text-muted-color">{{ source }}</span>
        </div>
        <div style="height: 180px">
            <Chart type="bar" :data="chartData" :options="chartOptions" style="height: 100%" />
        </div>
    </div>
</template>
