<script setup>
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import { MEASURE_STATUS } from '@/config/measureStatus';
import { ruDistrictName } from '@/utils/districtNames';
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
    priorityNote: { type: String, default: 'скор риска (0–100) × lg(население). Шкала приоритета не 0–100 (максимум ≈ 550): крупный НП встаёт в очереди выше малого села с тем же скором — цена ошибки выше' }
});
// show-measures — «показать все меры этого объекта»: страница закрывает диалог,
// выбирает объект на карте и фильтрует очередь по нему
defineEmits(['update:visible', 'show-measures']);

// какое правило породило меру — по точному совпадению формулировки
const triggeredRule = computed(() => props.rules.find((r) => r.title === props.measure?.title) ?? null);

// Меры накопительные: объект получает все ступени, чей порог пройден его скором.
// Показываем именно назначенные меры (по нарастанию порога, текущая выделена),
// а непройденные пороги — одной строкой-сноской, чтобы не путать «советами».
const assignedRules = computed(() =>
    props.rules
        .filter((r) => props.score !== null && props.score >= r.minScore)
        .sort((a, b) => a.minScore - b.minScore)
        .map((r) => ({ ...r, isThis: triggeredRule.value?.title === r.title }))
);
const notReachedRules = computed(() => props.rules.filter((r) => props.score !== null && props.score < r.minScore).sort((a, b) => a.minScore - b.minScore));
const decidedAtLabel = computed(() => (props.measure?.decidedAt ? new Date(props.measure.decidedAt).toLocaleString('ru-RU') : null));
// имя объекта: у паводков settlementName, у районных мер — districtName (латиница из geojson → русское)
const entityName = computed(() => ruDistrictName(props.measure?.settlementName || props.measure?.districtName || '—'));
</script>

<template>
    <Dialog :visible="visible" modal header="Почему рекомендовано" :style="{ width: '34rem', maxWidth: '95vw' }" :dismissableMask="true" @update:visible="$emit('update:visible', $event)">
        <template v-if="measure">
            <div class="exp-title">{{ measure.title }}</div>
            <div class="exp-meta">
                <span>{{ entityLabel }}: <span class="exp-entity">{{ entityName }}</span></span>
                <RiskScoreBadge v-if="score !== null" :score="score" />
                <Tag :value="MEASURE_STATUS[measure.status]?.label ?? measure.status" :severity="MEASURE_STATUS[measure.status]?.severity ?? 'secondary'" />
            </div>

            <div class="exp-section">Почему рекомендовано</div>
            <p class="exp-text">
                Порог меры — скор <strong>≥ {{ triggeredRule?.minScore ?? '—' }}</strong>, скор объекта — <strong>{{ score ?? '—' }}</strong> → черновик создан.
            </p>

            <template v-if="assignedRules.length">
                <div class="exp-section">Предложено этому объекту ({{ assignedRules.length }})</div>
                <p class="exp-text text-muted-color exp-ladder-note">По каждой мере комиссия решает отдельно. ✓ — открытая сейчас.</p>
                <ul class="exp-list">
                    <li v-for="r in assignedRules" :key="r.title" class="exp-row" :class="{ 'exp-row--hit': r.isThis }">
                        <span class="exp-label">
                            <i v-if="r.isThis" class="pi pi-check-circle exp-check"></i>
                            {{ r.title }}
                        </span>
                    </li>
                </ul>
                <p v-if="notReachedRules.length" class="exp-text text-muted-color exp-ladder-note">
                    Не предложены: {{ notReachedRules.map((r) => `${r.title} (≥ ${r.minScore})`).join('; ') }}.
                </p>
                <Button label="Все меры этого объекта в очереди" icon="pi pi-filter" text size="small" class="exp-filter-btn" @click="$emit('show-measures', measure)" />
            </template>

            <div class="exp-section">Из чего складывается скор</div>
            <ul v-if="factors.length" class="exp-list">
                <li v-for="f in factors" :key="f.name" class="exp-row">
                    <span class="exp-label">{{ f.name }}</span>
                    <Tag :value="f.display" :severity="f.severity ?? 'secondary'" />
                </li>
            </ul>
            <p v-else class="exp-text text-muted-color">Разбор скора недоступен для этого объекта.</p>

            <div class="exp-section">Приоритет в очереди</div>
            <p class="exp-text"><Tag :value="Math.round(measure.priority * 10) / 10" severity="info" /> — {{ priorityNote }}.</p>

            <template v-if="measure.decidedByName">
                <div class="exp-section">Решение</div>
                <p class="exp-text">
                    {{ MEASURE_STATUS[measure.status]?.label ?? measure.status }} — {{ measure.decidedByName }}<template v-if="decidedAtLabel">, {{ decidedAtLabel }}</template>
                    <template v-if="measure.note"><br /><span class="text-muted-color">«{{ measure.note }}»</span></template>
                </p>
            </template>

            <p class="exp-footnote">AI предлагает — решение принимает комиссия.</p>
        </template>
    </Dialog>
</template>

<style scoped>
/* Собственная типографика диалога: классы карточки карты (:slotted в
   RiskEntityCard) здесь не действуют — раньше секции оставались нестилизованными */
.exp-title {
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 10px;
}
.exp-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 13px;
    color: var(--text-color-secondary);
    padding-bottom: 14px;
    border-bottom: 1px solid var(--surface-border);
}
.exp-section {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-color);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin: 16px 0 8px;
}
.exp-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
}
.exp-list {
    list-style: none;
    padding: 0;
    margin: 8px 0 0;
    display: flex;
    flex-direction: column;
    gap: 7px;
}
.exp-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}
.exp-row--muted {
    opacity: 0.5;
}
.exp-row--hit {
    opacity: 1;
    font-weight: 600;
}
.exp-ladder-note {
    margin-top: 4px;
    font-size: 12px;
    line-height: 1.45;
}
.exp-entity {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-color);
}
.exp-filter-btn {
    margin-top: 8px;
    padding-left: 0;
}
.exp-label {
    font-size: 13px;
    color: #475467;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
}
.exp-check {
    font-size: 18px;
    color: var(--green-500, #22c55e);
    font-weight: 700;
}
.exp-footnote {
    font-size: 11px;
    color: #98a2b3;
    line-height: 1.5;
    margin: 16px 0 0;
    padding-top: 12px;
    border-top: 1px solid var(--surface-border);
}
</style>
