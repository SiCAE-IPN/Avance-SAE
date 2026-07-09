
function cerrarBannerRechazo() {
    const banner = document.getElementById('banner-rechazo');
    if (banner) banner.style.display = 'none';
}

function togglePanelNotificaciones() {
    const panel = document.getElementById('panel-notificaciones');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
}

function mostrarBannerRechazo() {
    const banner = document.getElementById('banner-rechazo');
    if (banner) {
        banner.style.display = 'flex';
        const panel = document.getElementById('panel-notificaciones');
        if (panel) panel.style.display = 'none';
    }
}

function actualizarContadorPanel() {
    const textarea = document.getElementById('motivo-rechazo-panel');
    const contador = document.getElementById('contador-caracteres-panel');
    if (textarea && contador) {
        contador.textContent = textarea.value.length;
    }
}

function cerrarPanelRechazo() {
    const panel = document.getElementById('panel-rechazo');
    if (panel) panel.style.display = 'none';
}
