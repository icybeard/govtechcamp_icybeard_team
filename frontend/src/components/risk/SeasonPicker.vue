<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

/**
 * Переключатель сезона — как в макете: подпись сезона между стрелками ← →,
 * клик по подписи открывает свой список (не нативный <select>, без иконки
 * шеврона). Закрывается по клику вовне.
 */
const props = defineProps({
    modelValue: { type: String, required: true },
    options: { type: Array, required: true } // [{ label, value }]
});
const emit = defineEmits(['update:modelValue']);

const open = ref(false);
const root = ref(null);

const index = computed(() => props.options.findIndex((o) => o.value === props.modelValue));
const currentLabel = computed(() => props.options[index.value]?.label ?? '');
const atStart = computed(() => index.value <= 0);
const atEnd = computed(() => index.value === -1 || index.value >= props.options.length - 1);

function step(delta) {
    const next = props.options[index.value + delta];
    if (next) emit('update:modelValue', next.value);
}
function select(value) {
    emit('update:modelValue', value);
    open.value = false;
}
function onDocClick(e) {
    if (open.value && root.value && !root.value.contains(e.target)) open.value = false;
}
onMounted(() => document.addEventListener('mousedown', onDocClick));
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick));
</script>

<template>
    <div ref="root" class="season-picker" :class="{ 'season-picker--open': open }">
        <button type="button" class="season-picker__arrow" :disabled="atStart" aria-label="Предыдущий сезон" @click="step(-1)">←</button>
        <button type="button" class="season-picker__label" @click="open = !open">{{ currentLabel }}</button>
        <button type="button" class="season-picker__arrow" :disabled="atEnd" aria-label="Следующий сезон" @click="step(1)">→</button>

        <div v-if="open" class="season-picker__menu">
            <div v-for="(opt, i) in options" :key="opt.value" class="season-picker__option" :class="{ 'season-picker__option--active': i === index }" @click="select(opt.value)">
                {{ opt.label }}
            </div>
        </div>
    </div>
</template>

<style scoped>
.season-picker {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 14px;
    border: 1px solid var(--surface-border);
    border-radius: 10px;
    padding: 8px 14px;
}
.season-picker--open {
    border-color: #2461c9;
}
.season-picker__arrow {
    border: none;
    background: none;
    padding: 0;
    color: #98a2b3;
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
}
.season-picker__arrow:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}
.season-picker__label {
    border: none;
    background: none;
    padding: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
    cursor: pointer;
    white-space: nowrap;
}
.season-picker__menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    min-width: 240px;
    border: 1px solid var(--surface-border);
    border-radius: 10px;
    box-shadow: 0 8px 20px rgba(16, 24, 40, 0.12);
    overflow: hidden;
    background: var(--surface-card);
    z-index: 10;
}
.season-picker__option {
    padding: 9px 14px;
    font-size: 13px;
    color: var(--text-color-secondary);
    border-top: 1px solid var(--surface-border);
    cursor: pointer;
}
.season-picker__option:first-child {
    border-top: none;
}
.season-picker__option--active {
    font-weight: 600;
    background: #eaf2ff;
    color: #2461c9;
}
</style>
