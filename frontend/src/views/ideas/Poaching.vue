<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { ref } from 'vue';

// Идея в проработке: данных пока нет, карта без заливки.
const selected = ref(null);
</script>

<template>
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h4 class="m-0">Мониторинг браконьерства</h4>
                        <span class="text-muted-color">Идея в проработке — см. docs/ideas/poaching/.</span>
                    </div>
                    <Tag value="концепция" severity="info" />
                </div>
            </div>
        </div>

        <div class="col-span-12 lg:col-span-8">
            <div class="card mb-0">
                <KazakhstanMap legend-title="Инциденты" @region-click="selected = $event" />
            </div>
        </div>

        <div class="col-span-12 lg:col-span-4">
            <div class="card mb-0 h-full">
                <h5>Что нужно определить</h5>
                <ul class="list-disc pl-6 leading-loose">
                    <li>Пользователь: инспектор охотхозяйства? комитет лесного хозяйства?</li>
                    <li>Источники данных: снимки, треки, сообщения граждан?</li>
                    <li>AI-компонент и его объяснимость</li>
                    <li>Реализуемость прототипа до 17.07.2026</li>
                </ul>
                <p v-if="selected" class="mt-4">
                    Выбран регион: <strong>{{ selected.name }}</strong>
                </p>
            </div>
        </div>
    </div>
</template>
