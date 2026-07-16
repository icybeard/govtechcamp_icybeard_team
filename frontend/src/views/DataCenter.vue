<script setup>
import { api } from '@/service/api';
import { isAdmin } from '@/service/auth';
import { useToast } from 'primevue/usetoast';
import { computed, onMounted, ref } from 'vue';

/**
 * Страница «Данные»: загрузка датасетов для обучения моделей и пересчёта рисков.
 * flood-scores (CSV формата scripts/load_scores.py) ингестируется сразу — карта
 * паводков выбранного сезона пересчитывается; остальные типы попадают в реестр
 * и используются офлайн-пайплайном ML (make-цели). Загрузка/удаление — Admin.
 */
const KINDS = [
    { value: 'flood-scores', label: 'Скоры паводков (CSV)', hint: 'name,lat,lon,score,factors_json — сразу пересчитывает карту сезона', ingest: true },
    { value: 'settlements', label: 'Справочник НП (CSV)', hint: 'name,lat,lon,population — офлайн-пайплайн', ingest: false },
    { value: 'fire-ml', label: 'Прогноз пожаров (JSON)', hint: 'формат fire-ml-today.json — офлайн-пайплайн', ingest: false },
    { value: 'winter-districts', label: 'Зимние индексы районов (JSON)', hint: 'формат winter-districts.json — офлайн-пайплайн', ingest: false },
    { value: 'training-raw', label: 'Сырые данные для обучения', hint: 'CSV/JSON — реестр для переобучения моделей', ingest: false }
];

const toast = useToast();

const files = ref([]);
const loading = ref(true);
const uploading = ref(false);

const kind = ref('flood-scores');
const period = ref('');
const note = ref('');
const selectedFile = ref(null);
const fileInput = ref(null);

const kindMeta = computed(() => KINDS.find((k) => k.value === kind.value));
const kindLabel = (value) => KINDS.find((k) => k.value === value)?.label ?? value;

function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

async function loadFiles() {
    try {
        files.value = await api.get('/datasets/');
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Не удалось загрузить реестр', detail: e.message, life: 5000 });
    } finally {
        loading.value = false;
    }
}
onMounted(loadFiles);

function onFilePick(event) {
    selectedFile.value = event.target.files?.[0] ?? null;
}

async function uploadFile() {
    if (!selectedFile.value) return;
    uploading.value = true;
    try {
        const form = new FormData();
        form.append('file', selectedFile.value);
        form.append('kind', kind.value);
        form.append('period', period.value.trim());
        form.append('note', note.value.trim());
        const result = await api.upload('/datasets/upload', form);
        toast.add({
            severity: 'success',
            summary: result.ingestedRows ? `Загружено, обновлено НП: ${result.ingestedRows}` : 'Файл загружен в реестр',
            detail: result.ingestedRows ? `Карта паводков сезона «${result.period || 'актуальный'}» пересчитана` : undefined,
            life: 6000
        });
        selectedFile.value = null;
        note.value = '';
        if (fileInput.value) fileInput.value.value = '';
        await loadFiles();
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Ошибка загрузки', detail: e.message, life: 6000 });
    } finally {
        uploading.value = false;
    }
}

async function removeFile(row) {
    try {
        await api.delete(`/datasets/${row.id}`);
        files.value = files.value.filter((f) => f.id !== row.id);
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Не удалось удалить', detail: e.message, life: 5000 });
    }
}
</script>

<template>
    <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12">
            <div class="card mb-0">
                <h4 class="mb-1">Данные</h4>
                <p class="text-muted-color mt-0 mb-0">
                    Загрузка датасетов для обучения моделей и пересчёта рисков. Скоры паводков применяются сразу; остальные наборы попадают в реестр и используются офлайн-пайплайном ML (make-цели — см. README).
                </p>
            </div>
        </div>

        <div v-if="isAdmin" class="col-span-12">
            <div class="card mb-0">
                <h5 class="mb-4">Загрузить набор</h5>
                <div class="flex flex-wrap items-end gap-4">
                    <div class="flex flex-col gap-1">
                        <label class="text-muted-color" for="dsKind">Тип набора</label>
                        <Select v-model="kind" inputId="dsKind" :options="KINDS" optionLabel="label" optionValue="value" style="min-width: 240px" />
                    </div>
                    <div class="flex flex-col gap-1">
                        <label class="text-muted-color" for="dsPeriod">Сезон (period)</label>
                        <InputText v-model="period" id="dsPeriod" placeholder="напр. 2024; пусто — актуальные" style="width: 220px" />
                    </div>
                    <div class="flex flex-col gap-1 grow">
                        <label class="text-muted-color" for="dsNote">Примечание</label>
                        <InputText v-model="note" id="dsNote" placeholder="источник, версия, комментарий" />
                    </div>
                </div>
                <div class="flex flex-wrap items-center gap-4 mt-4">
                    <input ref="fileInput" type="file" accept=".csv,.json" @change="onFilePick" />
                    <Button label="Загрузить" icon="pi pi-upload" :disabled="!selectedFile" :loading="uploading" @click="uploadFile" />
                </div>
                <Message severity="secondary" :closable="false" class="mt-4">{{ kindMeta.hint }}. Файлы .csv/.json до 50 МБ.</Message>
            </div>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <h5 class="mb-3">Реестр наборов</h5>
                <DataTable :value="files" :loading="loading" paginator :rows="10" size="small" sortField="uploadedAt" :sortOrder="-1">
                    <Column field="fileName" header="Файл" sortable />
                    <Column field="kind" header="Тип" sortable>
                        <template #body="{ data }">{{ kindLabel(data.kind) }}</template>
                    </Column>
                    <Column field="period" header="Сезон" style="width: 7rem">
                        <template #body="{ data }">{{ data.period || '—' }}</template>
                    </Column>
                    <Column field="size" header="Размер" style="width: 7rem">
                        <template #body="{ data }">{{ formatSize(data.size) }}</template>
                    </Column>
                    <Column field="ingestedRows" header="Ингест" style="width: 9rem">
                        <template #body="{ data }">
                            <Tag v-if="data.ingestedRows" :value="`обновлено НП: ${data.ingestedRows}`" severity="success" />
                            <span v-else class="text-muted-color">реестр</span>
                        </template>
                    </Column>
                    <Column field="uploadedByName" header="Загрузил" style="width: 10rem">
                        <template #body="{ data }">{{ data.uploadedByName ?? '—' }}</template>
                    </Column>
                    <Column field="uploadedAt" header="Когда" sortable style="width: 11rem">
                        <template #body="{ data }">{{ new Date(data.uploadedAt).toLocaleString('ru-RU') }}</template>
                    </Column>
                    <Column field="note" header="Примечание">
                        <template #body="{ data }">{{ data.note ?? '—' }}</template>
                    </Column>
                    <Column v-if="isAdmin" header="" style="width: 4rem">
                        <template #body="{ data }">
                            <Button icon="pi pi-trash" size="small" text severity="danger" @click="removeFile(data)" />
                        </template>
                    </Column>
                    <template #empty>Наборов пока нет — загрузите первый файл.</template>
                </DataTable>
            </div>
        </div>
    </div>
</template>
