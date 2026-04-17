// static/js/sidebar.js

// Configuración de menús por módulo
const menuConfig = {
    'matricula': {
        nombre: 'Matrícula',
        items: [
            { label: 'Consulta', icon: '🔍', url: '/matricula/consulta' },
            { label: 'Resumen', icon: '📊', url: '/matricula/resumen' }
        ]
    },
    'egresados': {
        nombre: 'Egresados',
        items: [
            { label: 'Consulta', icon: '🔍', url: '/egresados/consulta' },
            { label: 'Resumen', icon: '📊', url: '/egresados/resumen' }
        ]
    },
    'aprovechamiento': {
        nombre: 'Aprovechamiento',
        items: [
            { label: 'Consulta', icon: '🔍', url: '/aprovechamiento/consulta' },
            { label: 'Resumen', icon: '📊', url: '/aprovechamiento/resumen' }
        ]
    },
    'usuarios': {
        nombre: 'Catálogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Académica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' },
            { label: 'Programas', icon: '📚', url: '/programas' },
            { label: 'Semáforo', icon: '🚦', url: '/semaforo' }
        ]
    },
    'domicilios': {
        nombre: 'Catálogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Académica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' },
            { label: 'Programas', icon: '📚', url: '/programas' },
            { label: 'Semáforo', icon: '🚦', url: '/semaforo' }
        ]
    },
    'periodos': {
        nombre: 'Catálogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Académica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' },
            { label: 'Programas', icon: '📚', url: '/programas' },
            { label: 'Semáforo', icon: '🚦', url: '/semaforo' }
        ]
    },
    'programas': {
        nombre: 'Catálogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Académica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' },
            { label: 'Programas', icon: '📚', url: '/programas' },
            { label: 'Semáforo', icon: '🚦', url: '/semaforo' }
        ]
    },
    'semaforo': {
        nombre: 'Catálogos',
        items: [
            { label: 'Usuarios', icon: '👥', url: '/usuarios' },
            { label: 'Unidad Académica', icon: '🏢', url: '/domicilios' },
            { label: 'Periodos', icon: '📅', url: '/periodos' },
            { label: 'Programas', icon: '📚', url: '/programas' },
            { label: 'Semáforo', icon: '🚦', url: '/semaforo' }
        ]
    }
};

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarCloseMobile = document.getElementById('sidebarCloseMobile');
    const sidebarNav = document.getElementById('sidebarNav');
    const moduleName = document.getElementById('moduleName');

    if (!sidebar) return; // Si no existe sidebar, no hacer nada

    // ===== Detección inteligente de módulo y página =====
    const pathname = window.location.pathname;
    let moduloActual = null;
    let paginaActual = null;

    // Detectar el módulo actual
    for (let mod in menuConfig) {
        if (pathname.includes('/' + mod)) {
            moduloActual = mod;
            break;
        }
    }

    // Si encontramos el módulo, llenar el menú
    if (moduloActual && menuConfig[moduloActual]) {
        const config = menuConfig[moduloActual];
        moduleName.textContent = config.nombre;

        // Crear items del nav
        const items = config.items.map(item => {
            // Determinar si está activo (coincidencia exacta o parcial inteligente)
            const isActive = 
                pathname === item.url || 
                (pathname.includes(item.url) && item.url !== '/usuarios') ||
                (pathname.includes('resumen') && item.url.includes('resumen'));

            return `
                <a href="${item.url}" class="sidebar-item ${isActive ? 'active' : ''}">
                    <i>${item.icon}</i><span>${item.label}</span>
                </a>
            `;
        }).join('');

        sidebarNav.innerHTML = items;

        // Actualizar el estado activo después de renderizar
        updateActiveLink();
    }

    // Detectar si es móvil
    const isMobile = window.innerWidth <= 768;

    // Alternar sidebar en móvil
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('active');
        });
    }

    // Cerrar sidebar al hacer click en overlay
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    }

    // Cerrar sidebar con botón X en móvil
    if (sidebarCloseMobile) {
        sidebarCloseMobile.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    }

    // Cerrar sidebar al seleccionar un item (en móvil)
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    sidebarItems.forEach(item => {
        item.addEventListener('click', function() {
            if (isMobile && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                sidebarOverlay.classList.remove('active');
            }
        });
    });

    // Ajustar responsivo en resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        }
    });

    // Prevenir cierre de sidebar en desktop con ESC (en mobile sí cierra)
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && isMobile && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        }
    });
});

// Función para actualizar el link activo
function updateActiveLink() {
    const pathname = window.location.pathname;
    const links = document.querySelectorAll('.sidebar-item');

    links.forEach(link => {
        const href = link.getAttribute('href');
        
        // Lógica mejorada para determinar el link activo
        const isActive = 
            pathname === href ||
            (pathname.includes(href) && href.length > 1) ||
            (href.includes('resumen') && pathname.includes('resumen')) ||
            (href.includes('consulta') && pathname.includes('consulta'));

        if (isActive) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

    // Alternar sidebar en móvil
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('active');
        });
    }

    // Cerrar sidebar al hacer click en overlay
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    }

    // Cerrar sidebar con botón X en móvil
    if (sidebarCloseMobile) {
        sidebarCloseMobile.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    }

    // Cerrar sidebar al seleccionar un item (en móvil)
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    sidebarItems.forEach(item => {
        item.addEventListener('click', function() {
            if (isMobile && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                sidebarOverlay.classList.remove('active');
            }
        });
    });

    // Ajustar responsivo en resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            // En desktop, asegurar que esté cerrada la clase 'open' (ya que usa hover)
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        } else {
            // En mobile, asegurar que la clase 'open' esté controlada
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        }
    });

    // Prevenir cierre de sidebar en desktop con ESC (en mobile sí cierra)
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && isMobile && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        }
    });
});
