<script setup>
/** Плавающая подсказка над картой («Кликните НП/район — ...»). */
defineProps({
    text: { type: String, required: true }
});
</script>

<template>
    <div class="map-hint-badge">{{ text }}</div>
</template>

<style scoped>
.map-hint-badge {
    position: absolute;
    top: 1rem;
    right: 1rem;
    z-index: 1000;
    background: var(--surface-card);
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.15);
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color-secondary);
}
</style>
