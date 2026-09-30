// static/js/sidebar.js

const menuConfig = {
    matricula: {
        nombre: 'Matricula',
        items: [
            { label: 'Consulta', icon: '🔍', url: '/matricula/consulta' },
            { label: 'Acuses', icon: '📄', url: '/matricula/acuses' }
        ]
    },
    egresados: {
        nombre: 'Egresados',
        items: [
            { label: 'Consulta', icon: '🔍', url: '/egresados/consulta' },
        ]
    },
    aprovechamiento: {
        nombre: 'Aprovechamiento',
        items: [
            { label: 'Consulta', icon: '🔍', url: '/aprovechamiento/consulta' },
        ]
    },
    titulados: {
        nombre: 'Titulados',
        items: [
            { label: 'Consulta', icon: '🔍', url: '/titulados/consulta' },
        ]
    },
    usuarios: {
        nombre: 'Catalogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Academica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' }
        ]
    },
    domicilios: {
        nombre: 'Catalogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Academica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' }
        ]
    },
    periodos: {
        nombre: 'Catalogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Academica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' }
        ]
    }
};

function isActivePath(pathname, itemUrl) {
    if (pathname === itemUrl) {
        return true;
    }
    if (itemUrl === '/matricula/acuses' && pathname.startsWith('/matricula/acuses')) {
        return true;
    }
    return false;
}

document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) {
        return;
    }

    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarCloseMobile = document.getElementById('sidebarCloseMobile');
    const sidebarNav = document.getElementById('sidebarNav');
    const moduleName = document.getElementById('moduleName');

    const pathname = window.location.pathname;
    let moduloActual = null;

    Object.keys(menuConfig).forEach((modulo) => {
        if (!moduloActual && pathname.includes(`/${modulo}`)) {
            moduloActual = modulo;
        }
    });

    if (moduloActual && menuConfig[moduloActual] && sidebarNav) {
        const config = menuConfig[moduloActual];
        if (moduleName) {
            moduleName.textContent = config.nombre;
        }

        sidebarNav.innerHTML = config.items
            .map((item) => {
                const active = isActivePath(pathname, item.url) ? 'active' : '';
                return `
                    <a href="${item.url}" class="sidebar-item ${active}">
                        <i>${item.icon}</i><span>${item.label}</span>
                    </a>
                `;
            })
            .join('');
    }

    const isMobileViewport = () => window.innerWidth <= 768;
    const closeSidebar = () => {
        sidebar.classList.remove('open');
        if (sidebarOverlay) {
            sidebarOverlay.classList.remove('active');
        }
    };

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('open');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('active');
            }
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebar);
    }

    if (sidebarCloseMobile) {
        sidebarCloseMobile.addEventListener('click', (e) => {
            e.stopPropagation();
            closeSidebar();
        });
    }

    document.querySelectorAll('.sidebar-item').forEach((item) => {
        item.addEventListener('click', () => {
            if (isMobileViewport()) {
                closeSidebar();
            }
        });
    });

    window.addEventListener('resize', () => {
        if (!isMobileViewport()) {
            closeSidebar();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isMobileViewport() && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });
});
