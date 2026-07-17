<script setup>
import AppLogo from '@/components/AppLogo.vue';
import { login } from '@/service/auth';
import { useToast } from 'primevue/usetoast';
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const email = ref('');
const password = ref('');
const checked = ref(false);
const loading = ref(false);

const router = useRouter();
const route = useRoute();
const toast = useToast();

async function signIn() {
    loading.value = true;
    try {
        await login(email.value, password.value);
        router.push(route.query.redirect ?? '/');
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Не удалось войти', detail: e.message, life: 5000 });
    } finally {
        loading.value = false;
    }
}
</script>

<template>
    <div class="bg-surface-50 dark:bg-surface-950 flex items-center justify-center min-h-screen min-w-[100vw] overflow-hidden">
        <div class="flex flex-col items-center justify-center">
            <div style="border-radius: 56px; padding: 0.3rem; background: linear-gradient(180deg, var(--primary-color) 10%, rgba(33, 150, 243, 0) 30%)">
                <div class="w-full bg-surface-0 dark:bg-surface-900 py-20 px-8 sm:px-20" style="border-radius: 53px">
                    <div class="text-center mb-8">
                        <AppLogo :size="64" class="mb-6 mx-auto" style="display: block" />
                        <div class="text-surface-900 dark:text-surface-0 text-3xl font-medium mb-2">IcyBeard</div>
                        <div class="text-muted-color mb-4">Платформа превентивного управления природными рисками</div>
                        <span class="text-muted-color font-medium">Войдите, чтобы продолжить</span>
                    </div>

                    <div>
                        <label for="email1" class="block text-surface-900 dark:text-surface-0 text-xl font-medium mb-2">Email</label>
                        <InputText id="email1" type="text" placeholder="Электронная почта" class="w-full md:w-[30rem] mb-8" v-model="email" />

                        <label for="password1" class="block text-surface-900 dark:text-surface-0 font-medium text-xl mb-2">Пароль</label>
                        <Password id="password1" v-model="password" placeholder="Пароль" :toggleMask="true" class="mb-4" fluid :feedback="false"></Password>

                        <div class="flex items-center justify-between mt-2 mb-8 gap-8">
                            <div class="flex items-center">
                                <Checkbox v-model="checked" id="rememberme1" binary class="mr-2"></Checkbox>
                                <label for="rememberme1">Запомнить меня</label>
                            </div>
                            
                        </div>
                        <Button label="Войти" class="w-full" :loading="loading" @click="signIn"></Button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.pi-eye {
    transform: scale(1.6);
    margin-right: 1rem;
}

.pi-eye-slash {
    transform: scale(1.6);
    margin-right: 1rem;
}
</style>
