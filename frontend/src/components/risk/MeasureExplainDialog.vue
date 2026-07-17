<script setup>
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import { MEASURE_STATUS } from '@/config/measureStatus';
import { computed } from 'vue';

/**
 * «Почему рекомендовано» — прозрачность рекомендации для комиссии:
 * правило генерации (порог и скор на момент создания черновика — из Description),
 * разбор скора по факторам (SHAP у паводков, слагаемые метео-индекса у пожаров,
 * субиндексы у зимы), формула приоритета и аудит решения.
 * Компонент только отображает: данные собирает страница контура.
 */
const props = defineProps({
    visible: { type: Boolean, default: false },
    measure: { type: Object, default: null },
    entityLabel: { type: String, default: 'НП' },
    score: { type: Number, default: null }, // текущий скор объекта на странице
    factors: { type: Array, default: () => [] }, // [{ name, display, severity }]
    rules: { type: Array, default: () => [] }, // [{ minScore, title }] — правила модуля
    priorityNote: { type: String, default: 'скор риска × lg(население)' }
});
defineEmits(['update:visible']);

// какое правило породило меру — по точному совпадению формулировки
const triggeredRule = computed(() => props.rules.find((r) => r.title === props.measure?.title) ?? null);
const decidedAtLabel = computed(() => (props.measure?.decidedAt ? new Date(props.measure.decidedAt).toLocaleString('ru-RU') : null));
</script>

<template>
    <Dialog :visible="visible" modal header="Почему рекомендовано" :style="{ width: '34rem', maxWidth: '95vw' }" :dismissableMask="true" @update:visible="$emit('update:visible', $event)">
        <template v-if="measure">
            <div class="explain-measure-title">{{ measure.title }}</div>
            <div class="risk-meta-row mb-4">
                {{ entityLabel }}: <strong>{{ measure.settlementName }}</strong>
                <template v-if="score !== null">
                    · текущий скор <RiskScoreBadge :score="score" />
                </template>
                <Tag :value="MEASURE_STATUS[measure.status]?.label ?? measure.status" :severity="MEASURE_STATUS[measure.status]?.severity ?? 'secondary'" />
            </div>

            <div class="risk-section-title">Правило генерации</div>
            <p class="mb-3 mt-0">{{ measure.description ?? 'Мера добавлена вручную — правило не применялось.' }}</p>
            <ul v-if="rules.length" class="list-none p-0 m-0 flex flex-col gap-1 mb-4">
                <li v-for="r in rules" :key="r.title" class="risk-metric-row explain-rule" :class="{ 'explain-rule--hit': triggeredRule?.title === r.title }">
                    <span class="risk-metric-label">
                        <i v-if="triggeredRule?.title === r.title" class="pi pi-check-circle" style="font-size: 12px"></i>
                        {{ r.title }}
                    </span>
                    <Tag :value="`скор ≥ ${r.minScore}`" :severity="triggeredRule?.title === r.title ? 'warn' : 'secondary'" />
                </li>
            </ul>

            <div class="risk-section-title">Из чего складывается скор</div>
            <ul v-if="factors.length" class="list-none p-0 m-0 flex flex-col gap-2 mb-4">
                <li v-for="f in factors" :key="f.name" class="risk-metric-row">
                    <span class="risk-metric-label">{{ f.name }}</span>
                    <Tag :value="f.display" :severity="f.severity ?? 'secondary'" />
                </li>
            </ul>
            <p v-else class="text-muted-color mb-4 mt-0">Разбор скора недоступен для этого объекта.</p>

            <div class="risk-section-title">Приоритет в очереди</div>
            <p class="mb-0 mt-0">
                <Tag :value="measure.priority" severity="info" /> — {{ priorityNote }}. Чем выше приоритет, тем раньше мера попадает на рассмотрение комиссии.
            </p>

            <template v-if="measure.decidedByName">
                <div class="risk-section-title mt-4">Решение</div>
                <p class="mb-0 mt-0">
                    {{ MEASURE_STATUS[measure.status]?.label ?? measure.status }} — {{ measure.decidedByName }}<template v-if="decidedAtLabel">, {{ decidedAtLabel }}</template>
                    <template v-if="measure.note"><br /><span class="text-muted-color">«{{ measure.note }}»</span></template>
                </p>
            </template>

            <p class="risk-footnote mt-4 mb-0">AI предлагает — решение принимает человек: черновик создан автоматически по порогу скора, утверждение остаётся за комиссией.</p>
        </template>
    </Dialog>
</template>

<style scoped>
.explain-measure-title {
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 10px;
}
.explain-rule {
    opacity: 0.75;
}
.explain-rule--hit {
    opacity: 1;
    font-weight: 600;
}
</style>
