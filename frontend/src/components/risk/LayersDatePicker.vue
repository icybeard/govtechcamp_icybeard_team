<script setup>
import { GIBS_MIN_DATE } from '@/service/gibs';
import { computed } from 'vue';

/**
 * Дата спутниковых слоёв GIBS (снимок, осадки, снег). Меняет ТОЛЬКО слои —
 * скоринг районов/НП остаётся по выбранному сезону, о чём говорит тултип.
 * Границы: старт архива IMERG (июнь 2000) … вчера (сегодняшние тайлы GIBS
 * ещё не обработаны).
 */
const props = defineProps({
    modelValue: { type: Date, required: true }
});
const emit = defineEmits(['update:modelValue']);

const maxDate = new Date(Date.now() - 24 * 3600 * 1000);

const model = computed({
    get: () => props.modelValue,
    set: (value) => {
        if (value) emit('update:modelValue', value);
    }
});
</script>

<template>
    <div v-tooltip.bottom="'Дата спутниковых слоёв (снимок, осадки, снег). На скоринг не влияет.'" class="flex items-center gap-2">
        <span class="text-muted-color">Слои:</span>
        <DatePicker v-model="model" size="small" dateFormat="dd.mm.yy" showIcon iconDisplay="input" :minDate="GIBS_MIN_DATE" :maxDate="maxDate" :manualInput="false" inputClass="layers-date-input" />
    </div>
</template>

<style>
.layers-date-input {
    width: 118px;
}
</style>
