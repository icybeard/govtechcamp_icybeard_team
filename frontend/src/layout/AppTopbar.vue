<script setup>
import AppLogo from '@/components/AppLogo.vue';
import { useLayout } from '@/layout/composables/layout';
import { logout } from '@/service/auth';
import { useRouter } from 'vue-router';

const { toggleMenu, toggleDarkMode, isDarkTheme } = useLayout();
const router = useRouter();

function signOut() {
    logout();
    router.push('/auth/login');
}
</script>

<template>
    <div class="layout-topbar">
        <div class="layout-topbar-logo-container">
            <button class="layout-menu-button layout-topbar-action" @click="toggleMenu">
                <i class="pi pi-bars"></i>
            </button>
            <router-link to="/" class="layout-topbar-logo">
                <AppLogo :size="34" />
                <span class="app-brand">
                    <span class="app-brand__name">ICYBEARD</span>
                    <span class="app-brand__tagline">природные риски</span>
                </span>
            </router-link>
        </div>

        <div class="layout-topbar-actions">
            <div class="layout-config-menu">
                <button type="button" class="layout-topbar-action" @click="toggleDarkMode">
                    <i :class="['pi', { 'pi-moon': isDarkTheme, 'pi-sun': !isDarkTheme }]"></i>
                </button>
            </div>

            <button
                class="layout-topbar-menu-button layout-topbar-action"
                v-styleclass="{ selector: '@next', enterFromClass: 'hidden', enterActiveClass: 'p-anchored-overlay-enter-active', leaveToClass: 'hidden', leaveActiveClass: 'p-anchored-overlay-leave-active', hideOnOutsideClick: true }"
            >
                <i class="pi pi-ellipsis-v"></i>
            </button>

            <div class="layout-topbar-menu hidden lg:block">
                <div class="layout-topbar-menu-content">
                    <button type="button" class="layout-topbar-action" @click="router.push('/account/settings')">
                        <i class="pi pi-user"></i>
                        <span>Настройки</span>
                    </button>
                    <button type="button" class="layout-topbar-action" @click="signOut">
                        <i class="pi pi-sign-out"></i>
                        <span>Выйти</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.app-brand {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
}
.app-brand__name {
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.08em;
}
.app-brand__tagline {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-color-secondary);
}
</style>
