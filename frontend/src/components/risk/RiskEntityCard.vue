<script setup>
/**
 * Плавающая карточка объекта над картой (НП/район) — общий каркас по макету:
 * цветная полоска контура сверху, мелкая серая подпись типа объекта, крупное
 * имя. Содержимое (скор, факторы, история) — в default-слоте, оформляется
 * готовыми классами .risk-meta-row / .risk-metric-row / .risk-metric-label /
 * .risk-section-title / .risk-footnote (стили — ниже, через :slotted).
 */
defineProps({
    entityLabel: { type: String, required: true }, // 'Населённый пункт' | 'Район'
    name: { type: String, required: true },
    color: { type: String, required: true }
});
defineEmits(['close']);
</script>

<template>
    <div class="risk-entity-card">
        <div class="risk-entity-card__accent" :style="{ background: color }" />
        <div class="risk-entity-card__body">
            <div class="risk-entity-card__header">
                <span class="risk-entity-card__eyebrow">{{ entityLabel }}</span>
                <button type="button" class="risk-entity-card__close" aria-label="Закрыть" @click="$emit('close')">×</button>
            </div>
            <div class="risk-entity-card__name">{{ name }}</div>
            <slot />
        </div>
    </div>
</template>

<style scoped>
.risk-entity-card {
    position: absolute;
    top: 1rem;
    right: 1rem;
    z-index: 1000;
    width: 300px;
    max-width: 85%;
    max-height: calc(100% - 2rem);
    overflow-y: auto;
    background: var(--surface-card);
    border-radius: 14px;
    box-shadow: 0 16px 40px rgba(16, 24, 40, 0.22);
}
.risk-entity-card__accent {
    height: 5px;
}
.risk-entity-card__body {
    padding: 18px 20px;
}
.risk-entity-card__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 2px;
}
.risk-entity-card__eyebrow {
    font-size: 12px;
    font-weight: 600;
    color: #98a2b3;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.risk-entity-card__close {
    border: none;
    background: none;
    padding: 0;
    font-size: 16px;
    line-height: 1;
    color: #98a2b3;
    cursor: pointer;
}
.risk-entity-card__name {
    font-size: 19px;
    font-weight: 700;
    margin-bottom: 12px;
}

/* Утилиты для содержимого слота — единая типографика карточки объекта во всех модулях */
:slotted(.risk-meta-row) {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 12px;
    color: #667085;
}
:slotted(.risk-metric-row) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}
:slotted(.risk-metric-label) {
    font-size: 13px;
    color: #475467;
}
:slotted(.risk-metric-value) {
    font-size: 13px;
    font-weight: 600;
}
:slotted(.risk-section-title) {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-color);
    margin-bottom: 8px;
}
:slotted(.risk-footnote) {
    font-size: 11px;
    color: #98a2b3;
    line-height: 1.4;
}
</style>
