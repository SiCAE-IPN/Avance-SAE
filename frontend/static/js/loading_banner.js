/**
 * ==========================================================================
 * SISTEMA GLOBAL DE CARGA INSTITUCIONAL
 * SiCAE - Sistema de Captura y Análisis de la Estadística
 * Diseño Cuadrangular Centrado • Fondo Blanco y Acentos Guinda
 * Mensajes Contextuales Progresivos Dinámicos
 * ==========================================================================
 */

(function () {
    'use strict';

    // Evitar múltiples inicializaciones si el script se carga más de una vez
    if (window.__SICAE_LOADING_BANNER_INITIALIZED__) {
        return;
    }
    window.__SICAE_LOADING_BANNER_INITIALIZED__ = true;

    // Estado interno
    let activeRequestsCount = 0;
    let manualHoldCount = 0;
    let messageStepInterval = null;
    let debounceTimer = null;
    let showTimestamp = 0;
    let isVisible = false;
    let currentModuleKey = 'general';
    let currentStepIndex = 0;
    let customMessagesList = null;

    // Elementos del DOM
    let overlayEl = null;
    let bannerEl = null;
    let titleEl = null;
    let messageEl = null;

    /**
     * Secuencias de mensajes progresivos contextuales por módulo
     */
    const MODULE_PROGRESSION = {
        matricula: {
            title: 'Cargando Módulo de Matrícula',
            steps: [
                'Consultando y preparando datos de matrícula estudiantil...',
                'Organizando información de programas, modalidades y turnos...',
                'Cargando desglose de semestres y grupos de edad...',
                'Verificando estados de captura y validaciones...',
                'Finalizando preparación de la matriz de matrícula...'
            ]
        },
        egresados: {
            title: 'Cargando Módulo de Egresados',
            steps: [
                'Consultando y preparando el control de generaciones...',
                'Cargando listado de generaciones y modalidades...',
                'Organizando datos de boletas y distribución por sexo...',
                'Verificando avance de validación de egresados...',
                'Finalizando preparación del módulo de egresados...'
            ]
        },
        aprovechamiento: {
            title: 'Cargando Aprovechamiento Académico',
            steps: [
                'Consultando y preparando estadísticas de aprovechamiento...',
                'Cargando distribución de calificaciones y asignaturas...',
                'Calculando promedios y porcentajes de acreditación...',
                'Verificando indicadores por periodo y unidad académica...',
                'Finalizando análisis de aprovechamiento escolar...'
            ]
        },
        titulados: {
            title: 'Cargando Módulo de Titulados',
            steps: [
                'Consultando y preparando el registro de alumnos titulados...',
                'Cargando opciones y modalidades de titulación...',
                'Organizando información por programas y periodos...',
                'Verificando registros de actas y constancias...',
                'Finalizando preparación del módulo de titulados...'
            ]
        },
        catalogos: {
            title: 'Cargando Catálogos',
            steps: [
                'Preparando la gestión de usuarios, programas y unidades...',
                'Consultando registros y asignaciones institucionales...',
                'Sincronizando permisos, roles y dependencias...',
                'Cargando tablas de administración...'
            ]
        },
        seguridad: {
            title: 'Cargando Auditoría y Seguridad',
            steps: [
                'Consultando bitácoras y registros de seguridad...',
                'Analizando historial de accesos y bloqueos activos...',
                'Generando métricas y registros de auditoría...'
            ]
        },
        general: {
            title: 'Por favor espere un momento',
            steps: [
                'Cargando datos y procesando la solicitud...',
                'Sincronizando información con el sistema central...',
                'Procesando un volumen amplio de información...',
                'La operación continúa en proceso, por favor espere...'
            ]
        }
    };

    /**
     * Mapeo de rutas a claves de módulo
     */
    function detectModuleKey(url) {
        if (!url || typeof url !== 'string') return 'general';
        const lower = url.toLowerCase();
        if (lower.includes('matricula')) return 'matricula';
        if (lower.includes('egresados')) return 'egresados';
        if (lower.includes('aprovechamiento')) return 'aprovechamiento';
        if (lower.includes('titulados')) return 'titulados';
        if (lower.includes('usuario') || lower.includes('domicilio') || lower.includes('periodo') || lower.includes('programa') || lower.includes('semaforo')) return 'catalogos';
        if (lower.includes('seguridad')) return 'seguridad';
        return 'general';
    }

    /**
     * Construye e inyecta la estructura HTML de la tarjeta de carga en el DOM
     */
    function initDOM() {
        if (document.getElementById('sicae-loading-banner')) {
            overlayEl = document.getElementById('sicae-loading-overlay');
            bannerEl = document.getElementById('sicae-loading-banner');
            titleEl = document.getElementById('sicae-loading-title');
            messageEl = document.getElementById('sicae-loading-message');
            return;
        }

        if (!document.body) {
            document.addEventListener('DOMContentLoaded', initDOM);
            return;
        }

        // Crear Overlay
        overlayEl = document.createElement('div');
        overlayEl.id = 'sicae-loading-overlay';
        overlayEl.className = 'sicae-loading-overlay';
        overlayEl.setAttribute('aria-hidden', 'true');

        // Crear Tarjeta Centrada Cuadrangular
        bannerEl = document.createElement('div');
        bannerEl.id = 'sicae-loading-banner';
        bannerEl.className = 'sicae-loading-banner';
        bannerEl.setAttribute('role', 'alert');
        bannerEl.setAttribute('aria-live', 'assertive');

        bannerEl.innerHTML = `
            <div class="sicae-loading-body">
                <div class="sicae-loading-icon-wrapper">
                    <div class="sicae-loading-spinner"></div>
                    <div class="sicae-loading-icon-pulse"></div>
                </div>
                <div class="sicae-loading-content">
                    <h4 class="sicae-loading-title" id="sicae-loading-title">Por favor espere un momento</h4>
                    <p class="sicae-loading-message" id="sicae-loading-message">Cargando datos y procesando la solicitud...</p>
                </div>
            </div>
            <div class="sicae-loading-progress-bar">
                <div class="sicae-loading-progress-line"></div>
            </div>
        `;

        document.body.appendChild(overlayEl);
        document.body.appendChild(bannerEl);

        titleEl = document.getElementById('sicae-loading-title');
        messageEl = document.getElementById('sicae-loading-message');
    }

    /**
     * Actualiza el texto con una transición suave
     */
    function setMessageSmoothly(newText) {
        if (!messageEl || messageEl.textContent === newText) return;
        messageEl.classList.add('is-fading');
        setTimeout(() => {
            if (messageEl) {
                messageEl.textContent = newText;
                messageEl.classList.remove('is-fading');
            }
        }, 220);
    }

    /**
     * Inicia la rotación de pasos progresivos
     */
    function startMessageProgression() {
        if (messageStepInterval) clearInterval(messageStepInterval);
        currentStepIndex = 0;

        const config = MODULE_PROGRESSION[currentModuleKey] || MODULE_PROGRESSION.general;
        const steps = customMessagesList && customMessagesList.length > 0 ? customMessagesList : config.steps;

        if (steps && steps.length > 0 && messageEl) {
            messageEl.textContent = steps[0];
        }

        messageStepInterval = setInterval(() => {
            if (!isVisible || !messageEl) return;
            currentStepIndex++;
            if (currentStepIndex < steps.length) {
                setMessageSmoothly(steps[currentStepIndex]);
            } else {
                // Mantener el último paso informativo activo
                setMessageSmoothly(steps[steps.length - 1]);
            }
        }, 3200);
    }

    /**
     * Muestra la tarjeta con soporte para secuencias de mensajes progresivos
     */
    function show(options = {}) {
        // 1. NUNCA mostrar si la petición o URL es de cierre de sesión
        if (options.url && isLogoutTarget(null, options.url)) {
            return;
        }

        // 2. NUNCA mostrar si SweetAlert2 está visible en pantalla
        if (typeof window.Swal === 'function' && typeof window.Swal.isVisible === 'function' && window.Swal.isVisible()) {
            return;
        }
        const swalContainer = document.querySelector('.swal2-container');
        if (swalContainer && (swalContainer.classList.contains('swal2-shown') || (document.body && document.body.classList.contains('swal2-shown')))) {
            return;
        }

        initDOM();
        if (!bannerEl || !overlayEl) return;

        const {
            moduleKey = null,
            title = null,
            message = null,
            steps = null,
            blocking = true
        } = options;

        if (moduleKey && MODULE_PROGRESSION[moduleKey]) {
            currentModuleKey = moduleKey;
        } else if (options.url) {
            currentModuleKey = detectModuleKey(options.url);
        } else if (!moduleKey) {
            currentModuleKey = 'general';
        }

        const config = MODULE_PROGRESSION[currentModuleKey] || MODULE_PROGRESSION.general;
        customMessagesList = steps || (message ? [message, ...config.steps.slice(1)] : null);

        if (titleEl) {
            titleEl.textContent = title || config.title;
        }

        if (!isVisible) {
            isVisible = true;
            showTimestamp = Date.now();

            if (blocking && overlayEl) {
                overlayEl.classList.add('is-visible');
            }
            bannerEl.classList.add('is-visible');

            startMessageProgression();
        } else if (title) {
            if (titleEl) titleEl.textContent = title;
            startMessageProgression();
        }
    }

    /**
     * Oculta suavemente respetando un tiempo mínimo de despliegue
     */
    function hide() {
        if (!isVisible) return;

        const minDisplayDuration = 300; // ms
        const elapsed = Date.now() - showTimestamp;
        const remaining = Math.max(0, minDisplayDuration - elapsed);

        setTimeout(() => {
            if (activeRequestsCount <= 0 && manualHoldCount <= 0) {
                forceHide();
            }
        }, remaining);
    }

    /**
     * Ocultación inmediata y reseteo de temporizadores
     */
    function forceHide() {
        isVisible = false;
        activeRequestsCount = 0;
        manualHoldCount = 0;
        customMessagesList = null;

        if (messageStepInterval) {
            clearInterval(messageStepInterval);
            messageStepInterval = null;
        }
        if (debounceTimer) {
            clearTimeout(debounceTimer);
            debounceTimer = null;
        }

        if (bannerEl) bannerEl.classList.remove('is-visible');
        if (overlayEl) overlayEl.classList.remove('is-visible');
    }

    // Exponer función para forzar ocultación desde otros módulos
    window.forceHideLoadingBanner = forceHide;

    // =========================================================================
    // DETECCIÓN DE CIERRE DE SESIÓN (LOGOUT)
    // =========================================================================
    function isLogoutTarget(element, url) {
        if (url && typeof url === 'string') {
            const lower = url.toLowerCase();
            if (lower.includes('logout') || lower.includes('cerrar_sesion') || lower.includes('cerrarsesion')) {
                return true;
            }
        }
        if (element && element instanceof Element) {
            if (element.closest('.sidebar-logout, .btn-cerrar-sesion, .btn-cerrar-externo, [href*="logout"], [action*="logout"]')) {
                return true;
            }
            const text = (element.textContent || '').trim().toLowerCase();
            if (text.includes('cerrar sesión') || text.includes('cerrar sesion') || text === 'salir' || text === 'logout') {
                return true;
            }
        }
        return false;
    }

    // =========================================================================
    // DETECCIÓN DE PETICIONES DE ACCIÓN / STORED PROCEDURES / BOTONES
    // =========================================================================
    function isActionOrSPEndpoint(url, method) {
        if (!url || typeof url !== 'string') return false;
        if (isLogoutTarget(null, url)) return true;
        const m = (method || 'GET').toUpperCase();
        if (m === 'POST' || m === 'PUT' || m === 'DELETE' || m === 'PATCH') {
            return true;
        }
        const lower = url.toLowerCase();
        return (
            lower.includes('guardar') ||
            lower.includes('actualizar') ||
            lower.includes('validar') ||
            lower.includes('finalizar') ||
            lower.includes('rechazar') ||
            lower.includes('eliminar') ||
            lower.includes('preparar') ||
            lower.includes('_sp') ||
            lower.includes('/sp/') ||
            lower.includes('acuse') ||
            lower.includes('pdf') ||
            lower.includes('restaurar')
        );
    }

    // =========================================================================
    // OBSERVADOR DE SWEETALERT2: NUNCA SOLAPAR NI CERRAR ALERTAS DEL USUARIO
    // =========================================================================
    const swalObserver = new MutationObserver(() => {
        const isSwal = (typeof window.Swal === 'function' && typeof window.Swal.isVisible === 'function' && window.Swal.isVisible()) ||
                       (document.body && document.body.classList.contains('swal2-shown')) ||
                       !!document.querySelector('.swal2-container.swal2-shown');
        if (isSwal && isVisible) {
            forceHide();
        }
    });

    if (document.body) {
        swalObserver.observe(document.body, { attributes: true, childList: true, subtree: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            if (document.body) {
                swalObserver.observe(document.body, { attributes: true, childList: true, subtree: true });
            }
        });
    }

    // =========================================================================
    // INTERCEPTOR DE FETCH (EXCLUYE LOGOUT, ACCIONES SP Y MODALES EXISTENTES)
    // =========================================================================
    const originalFetch = window.fetch;

    window.fetch = async function (...args) {
        const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
        const options = args[1] || {};
        const method = options.method || (args[0] && args[0].method) || 'GET';

        // 1. Excluir si se solicita supresión explícita o es logout
        const suppressBanner = options.suppressLoadingBanner || 
                               (options.headers && (options.headers['X-Suppress-Loading'] || options.headers['X-Skip-Loading'])) ||
                               isLogoutTarget(null, url);

        if (suppressBanner) {
            return originalFetch.apply(this, args);
        }

        // 2. EXCLUIR SI ES ACCIÓN DE BOTÓN / SP O SI SWEETALERT YA ESTÁ ACTIVO
        const isSwalActive = typeof window.Swal === 'function' && typeof window.Swal.isVisible === 'function' && window.Swal.isVisible();
        if (isSwalActive || isActionOrSPEndpoint(url, method)) {
            // No mostrar el banner global para no duplicar/interferir con los loaders y alertas existentes del módulo
            return originalFetch.apply(this, args);
        }

        const modKey = detectModuleKey(url);
        activeRequestsCount++;

        if (activeRequestsCount === 1) {
            if (debounceTimer) clearTimeout(debounceTimer);

            // Debounce de 180ms para consultas de lectura en background
            debounceTimer = setTimeout(() => {
                if (activeRequestsCount > 0 && !(typeof window.Swal === 'function' && typeof window.Swal.isVisible === 'function' && window.Swal.isVisible())) {
                    show({
                        moduleKey: modKey,
                        url: url,
                        blocking: true
                    });
                }
            }, 180);
        }

        try {
            const response = await originalFetch.apply(this, args);
            return response;
        } finally {
            activeRequestsCount = Math.max(0, activeRequestsCount - 1);
            if (activeRequestsCount === 0 && manualHoldCount === 0) {
                hide();
            }
        }
    };

    // =========================================================================
    // INTERCEPTOR DE FORMULARIOS TRADICIONALES (SUBMITS)
    // =========================================================================
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || !(form instanceof HTMLFormElement)) return;

        // Si el formulario indica que no debe mostrar banner o es de logout
        if (form.hasAttribute('data-no-loading') || form.classList.contains('no-loading-banner')) {
            return;
        }

        const formAction = form.getAttribute('action') || '';
        if (isLogoutTarget(form, formAction) || isActionOrSPEndpoint(formAction, 'POST')) {
            return;
        }

        const modKey = detectModuleKey(formAction);

        manualHoldCount++;
        show({
            moduleKey: modKey,
            url: formAction,
            blocking: true
        });
    }, true);

    // =========================================================================
    // INTERCEPTOR UNIVERSAL DE NAVEGACIÓN Y ENLACES (CLICS A MÓDULOS)
    // =========================================================================
    document.addEventListener('click', function (e) {
        // Si SweetAlert2 ya está activo, no realizar ninguna acción de carga
        if (typeof window.Swal === 'function' && typeof window.Swal.isVisible === 'function' && window.Swal.isVisible()) {
            forceHide();
            return;
        }

        // 1. Detectar clics en enlaces <a>
        const link = e.target.closest('a');
        if (link) {
            const href = link.getAttribute('href');
            const target = link.getAttribute('target');
            const download = link.hasAttribute('download');
            const noLoading = link.hasAttribute('data-no-loading') || link.classList.contains('no-loading-banner');

            // NUNCA mostrar banner en enlaces de cierre de sesión
            if (isLogoutTarget(link, href)) {
                return;
            }

            if (href && !href.startsWith('#') && !href.startsWith('javascript:') && !href.startsWith('mailto:') && !href.startsWith('tel:') && target !== '_blank' && !download && !noLoading) {
                // Micro-tick para dar oportunidad a que los listeners locales manejen confirmaciones (ej. SweetAlert)
                setTimeout(() => {
                    if (typeof window.Swal === 'function' && typeof window.Swal.isVisible === 'function' && window.Swal.isVisible()) {
                        forceHide();
                        return;
                    }
                    if (e.defaultPrevented) {
                        return;
                    }
                    const modKey = detectModuleKey(href);
                    manualHoldCount++;
                    show({
                        moduleKey: modKey,
                        url: href,
                        blocking: true
                    });
                }, 20);
            }
            return;
        }

        // 2. Detectar clics en botones de retorno o navegación general
        const navBtn = e.target.closest('.btn-volver, .btn-regresar, [data-nav]');
        if (navBtn) {
            const navUrl = navBtn.getAttribute('data-nav') || navBtn.getAttribute('onclick') || '';
            if (isLogoutTarget(navBtn, navUrl)) {
                return;
            }
            setTimeout(() => {
                if (typeof window.Swal === 'function' && typeof window.Swal.isVisible === 'function' && window.Swal.isVisible()) {
                    forceHide();
                    return;
                }
                if (e.defaultPrevented) {
                    return;
                }
                const modKey = detectModuleKey(navUrl);
                manualHoldCount++;
                show({
                    moduleKey: modKey,
                    url: navUrl,
                    title: 'Regresando...',
                    blocking: true
                });
            }, 20);
        }
    }, false);

    // =========================================================================
    // MANEJO DE CARGA INICIAL DE RECURSOS DEL MÓDULO (BLOQUEO HASTA ESTAR LISTO)
    // =========================================================================
    function checkInitialModuleLoad() {
        const path = window.location.pathname || '';
        const modKey = detectModuleKey(path);

        // Si entramos a un módulo específico del sistema
        if (modKey && modKey !== 'general') {
            manualHoldCount++;
            show({
                moduleKey: modKey,
                url: path,
                blocking: true
            });

            // Función para liberar cuando el módulo esté completamente listo
            const releaseInitialHold = () => {
                manualHoldCount = Math.max(0, manualHoldCount - 1);
                hide();
            };

            // Escuchar evento personalizado de módulo listo
            window.addEventListener('sicae:module-ready', releaseInitialHold, { once: true });
            document.addEventListener('sicae:module-ready', releaseInitialHold, { once: true });

            // Escuchar window 'load' (cuando todos los recursos, scripts y assets terminaron)
            if (document.readyState === 'complete') {
                setTimeout(releaseInitialHold, 300);
            } else {
                window.addEventListener('load', () => {
                    setTimeout(releaseInitialHold, 300);
                }, { once: true });
            }

            // Fallback de seguridad para no dejar la pantalla bloqueada indefinidamente
            setTimeout(() => {
                if (manualHoldCount > 0) {
                    manualHoldCount = 0;
                    hide();
                }
            }, 6000);
        }
    }

    // =========================================================================
    // MANEJO DE CACHÉ DE NAVEGADOR (BFCACHE)
    // =========================================================================
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            forceHide();
        }
    });

    // =========================================================================
    // API PÚBLICA EXPUESTA EN WINDOW
    // =========================================================================
    window.showLoadingBanner = function (opts = {}) {
        manualHoldCount++;
        show(opts);
    };

    window.hideLoadingBanner = function () {
        manualHoldCount = Math.max(0, manualHoldCount - 1);
        if (manualHoldCount === 0 && activeRequestsCount === 0) {
            hide();
        }
    };

    window.forceHideLoadingBanner = function () {
        forceHide();
    };

    window.withLoadingBanner = async function (asyncFn, opts = {}) {
        window.showLoadingBanner(opts);
        try {
            return await asyncFn();
        } finally {
            window.hideLoadingBanner();
        }
    };

    // Inicializar DOM y evaluar carga de módulo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initDOM();
            checkInitialModuleLoad();
        });
    } else {
        initDOM();
        checkInitialModuleLoad();
    }
})();
