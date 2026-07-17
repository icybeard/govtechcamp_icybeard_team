import AppLayout from '@/layout/AppLayout.vue';
import { initAuth, isAuthenticated } from '@/service/auth';
import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            component: AppLayout,
            children: [
                {
                    path: '/',
                    name: 'dashboard',
                    component: () => import('@/views/Dashboard.vue')
                },
                {
                    path: '/risks',
                    name: 'risks',
                    component: () => import('@/views/RisksCenter.vue')
                },
                {
                    path: '/data',
                    name: 'data-center',
                    component: () => import('@/views/DataCenter.vue')
                },
                // старые пути — редиректы в единую страницу с нужным режимом
                { path: '/risks/flood', redirect: { path: '/risks', query: { mode: 'flood' } } },
                { path: '/risks/fire', redirect: { path: '/risks', query: { mode: 'fire' } } },
                { path: '/risks/winter', redirect: { path: '/risks', query: { mode: 'winter' } } },
                { path: '/ideas/flood-risk', redirect: { path: '/risks', query: { mode: 'flood' } } },
                { path: '/ideas/fire-risk', redirect: { path: '/risks', query: { mode: 'fire' } } },
                {
                    path: '/account/settings',
                    name: 'account-settings',
                    component: () => import('@/views/account/AccountSettings.vue')
                }
            ]
        },
        {
            path: '/auth/login',
            name: 'login',
            meta: { public: true },
            component: () => import('@/views/pages/auth/Login.vue')
        },
        {
            path: '/auth/access',
            name: 'accessDenied',
            meta: { public: true },
            component: () => import('@/views/pages/auth/Access.vue')
        },
        {
            path: '/auth/error',
            name: 'error',
            meta: { public: true },
            component: () => import('@/views/pages/auth/Error.vue')
        },
        {
            path: '/:pathMatch(.*)*',
            name: 'notfound',
            meta: { public: true },
            component: () => import('@/views/pages/NotFound.vue')
        }
    ]
});

router.beforeEach(async (to) => {
    await initAuth();
    if (!to.meta.public && !isAuthenticated.value) {
        return { name: 'login', query: { redirect: to.fullPath } };
    }
    return true;
});

export default router;
