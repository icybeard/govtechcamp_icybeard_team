<script setup>
import { computed } from 'vue';
import { riskBucket } from '@/utils/riskScore';

/** Числовой скор риска (0–100) на цветной подложке — 4 ступени, см. utils/riskScore. */
const props = defineProps({
    score: { type: Number, default: null },
    suffix: { type: String, default: '/ 100' },
    // 'md' — карточки объектов и таблицы; 'sm' — компактные списки на дашборде
    size: { type: String, default: 'md' }
});

const bucket = computed(() => riskBucket(props.score));
</script>

<template>
    <span v-if="bucket" class="risk-score-badge" :class="`risk-score-badge--${size}`" :style="{ background: bucket.bg, color: bucket.color }">{{ score }}{{ suffix ? ` ${suffix}` : '' }}</span>
    <span v-else class="text-muted-color">—</span>
</template>

<style scoped>
.risk-score-badge {
    font-weight: 700;
    white-space: nowrap;
}
.risk-score-badge--md {
    font-size: 14px;
    padding: 3px 10px;
    border-radius: 8px;
}
.risk-score-badge--sm {
    font-size: 12px;
    padding: 2px 9px;
    border-radius: 6px;
}
</style>
