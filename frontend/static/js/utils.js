// JavaScript común - Funciones reutilizables y utilidades

// Función para mostrar mensajes de éxito/error
function mostrarMensaje(mensaje, tipo = 'info') {
    const mensajeElement = document.getElementById('mensaje');
    if (mensajeElement) {
        const icono = tipo === 'success' ? '✅' : tipo === 'error' ? '❌' : 'ℹ️';
        const color = tipo === 'success' ? 'green' : tipo === 'error' ? 'red' : 'blue';
        mensajeElement.innerHTML = `<p style='color:${color};'>${icono} ${mensaje}</p>`;
    }
}

// Función para limpiar mensajes
function limpiarMensajes() {
    const mensajeElement = document.getElementById('mensaje');
    if (mensajeElement) {
        mensajeElement.innerHTML = '';
    }
}

// Función para mostrar/ocultar elementos
function toggleElement(elementId, show = null) {
    const element = document.getElementById(elementId);
    if (element) {
        if (show === null) {
            element.style.display = element.style.display === 'none' ? '' : 'none';
        } else {
            element.style.display = show ? '' : 'none';
        }
    }
}

// Función para limpiar errores visuales de inputs
function limpiarErroresVisuales() {
    document.querySelectorAll('.input-error').forEach(input => {
        input.classList.remove('input-error');
    });
}

// Función para validar email
function validarEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Función para formatear nombres (primera letra en mayúscula)
function formatearNombre(nombre) {
    return nombre.toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
}

// Purga automática de cookies obsoletas en el navegador (conservando únicamente session_id)
(function limpiarCookiesObsoletas() {
    try {
        const cookies = document.cookie.split(";");
        cookies.forEach(cookie => {
            const eqPos = cookie.indexOf("=");
            const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
            if (name && name !== "session_id") {
                document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
                document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=" + window.location.hostname;
            }
        });
    } catch (e) {}
})();

