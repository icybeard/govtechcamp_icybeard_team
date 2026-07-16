<script setup>
/**
 * Переключатель уровня детализации карты: «Регион» / «Населённый пункт».
 *
 * У каждого контура сейчас есть данные только на одном уровне — компонент
 * это отражает: недоступный вариант задизейблен с подсказкой, а не скрыт,
 * чтобы было видно, что уровень есть в принципе, просто пока не наполнен
 * данными. Как только модуль получит второй уровень (напр. пожары —
 * скоринг по НП), включается supports-пропом без правок разметки.
 */
const props = defineProps({
    modelValue: { type: String, required: true }, // 'region' | 'np'
    supportsRegion: { type: Boolean, default: true },
    supportsNp: { type: Boolean, default: true },
    regionLabel: { type: String, default: 'Регион' },
    npLabel: { type: String, default: 'Населённый пункт' },
    disabledReason: { type: String, default: 'Недоступно для этого слоя' }
});
const emit = defineEmits(['update:modelValue']);

function select(value, enabled) {
    if (enabled && value !== props.modelValue) emit('update:modelValue', value);
}
</script>

<template>
    <div class="granularity-switcher">
        <div
            class="granularity-option"
            :class="{ active: modelValue === 'region', disabled: !supportsRegion }"
            :title="supportsRegion ? '' : disabledReason"
            @click="select('region', supportsRegion)"
        >
            {{ regionLabel }}
        </div>
        <div class="granularity-option" :class="{ active: modelValue === 'np', disabled: !supportsNp }" :title="supportsNp ? '' : disabledReason" @click="select('np', supportsNp)">
            {{ npLabel }}
        </div>
    </div>
</template>

<style scoped>
.granularity-switcher {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--surface-hover);
    border-radius: 9px;
    padding: 4px;
}
.granularity-option {
    padding: 7px 14px;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color-secondary);
    cursor: pointer;
    white-space: nowrap;
}
.granularity-option.active {
    background: var(--surface-card);
    color: var(--text-color);
}
.granularity-option.disabled {
    color: var(--text-color-secondary);
    opacity: 0.5;
    cursor: not-allowed;
}
</style>
