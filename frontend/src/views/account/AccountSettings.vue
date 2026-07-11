<script setup>
import { changePassword, currentUser, updateProfile } from '@/service/auth';
import { useToast } from 'primevue/usetoast';
import { ref } from 'vue';

const toast = useToast();

const displayName = ref(currentUser.value?.displayName ?? '');
const savingProfile = ref(false);

const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const savingPassword = ref(false);

async function saveProfile() {
    savingProfile.value = true;
    try {
        await updateProfile(displayName.value);
        toast.add({ severity: 'success', summary: 'Профиль обновлён', life: 3000 });
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 5000 });
    } finally {
        savingProfile.value = false;
    }
}

async function savePassword() {
    if (newPassword.value !== confirmPassword.value) {
        toast.add({ severity: 'warn', summary: 'Пароли не совпадают', life: 4000 });
        return;
    }
    savingPassword.value = true;
    try {
        await changePassword(currentPassword.value, newPassword.value);
        currentPassword.value = newPassword.value = confirmPassword.value = '';
        toast.add({ severity: 'success', summary: 'Пароль изменён', life: 3000 });
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 5000 });
    } finally {
        savingPassword.value = false;
    }
}
</script>

<template>
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12 lg:col-span-6">
            <div class="card mb-0">
                <h5>Профиль</h5>
                <div class="flex flex-col gap-4 mt-4">
                    <div class="flex flex-col gap-2">
                        <label for="email">Email</label>
                        <InputText id="email" :model-value="currentUser?.email" disabled />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label for="displayName">Имя</label>
                        <InputText id="displayName" v-model="displayName" />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label>Роль</label>
                        <Tag :value="currentUser?.role ?? '—'" />
                    </div>
                    <Button label="Сохранить" :loading="savingProfile" class="w-fit" @click="saveProfile" />
                </div>
            </div>
        </div>

        <div class="col-span-12 lg:col-span-6">
            <div class="card mb-0">
                <h5>Смена пароля</h5>
                <div class="flex flex-col gap-4 mt-4">
                    <div class="flex flex-col gap-2">
                        <label for="currentPassword">Текущий пароль</label>
                        <Password id="currentPassword" v-model="currentPassword" :feedback="false" toggle-mask fluid />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label for="newPassword">Новый пароль</label>
                        <Password id="newPassword" v-model="newPassword" toggle-mask fluid />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label for="confirmPassword">Повторите новый пароль</label>
                        <Password id="confirmPassword" v-model="confirmPassword" :feedback="false" toggle-mask fluid />
                    </div>
                    <Button label="Изменить пароль" :loading="savingPassword" class="w-fit" @click="savePassword" />
                </div>
            </div>
        </div>
    </div>
</template>
