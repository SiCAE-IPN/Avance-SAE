/**
 * Panel de Validación Central (roles 6-9).
 *
 * Solo cambia la presentación: cada botón llama a los MISMOS endpoints (y por lo tanto
 * a los mismos SPs) que ya usaban las pantallas de acuse de cada módulo.
 * Filtros: Periodo + Nivel. Tabla: una fila por Unidad Académica con los 4 módulos.
 */
(function () {
    'use strict';

    const root = document.getElementById('vc-panel');
    if (!root) return;

    // ---- Endpoints existentes por módulo (sin cambios de lógica) ----------------
    // periodo_vc: indica a los endpoints de Aprovechamiento/Titulados el periodo elegido.
    const ACCIONES = {
        matricula: {
            validar: '/matricula/validar_semestre_rol',
            rechazar: '/matricula/rechazar_semestre_rol',
            payload: (c) => ({
                periodo: c.periodo, unidad: c.sigla, nivel: c.nivel,
                id_unidad_academica: c.idUnidad, id_nivel: c.idNivel,
            }),
        },
        aprovechamiento: {
            validar: '/aprovechamiento/validar',
            rechazar: '/aprovechamiento/rechazar',
            payload: (c) => ({
                periodo: c.periodo, periodo_vc: c.periodo, nivel: c.nivel, unidad_academica: c.sigla,
                id_unidad_academica: c.idUnidad,
            }),
        },
        egresados: {
            validar: '/egresados/validar',
            rechazar: '/egresados/rechazar',
            payload: (c) => ({
                periodo: c.periodo, unidad: c.sigla, nivel: c.nivel,
                id_unidad_academica: c.idUnidad, id_nivel: c.idNivel,
            }),
        },
        titulados: {
            validar: '/titulados/validar',
            rechazar: '/titulados/rechazar',
            payload: (c) => ({
                periodo: c.periodo, periodo_vc: c.periodo, unidad: c.sigla, nivel: c.nivel,
                id_unidad_academica: c.idUnidad, id_nivel: c.idNivel,
            }),
        },
    };

    const CLAVES = ['matricula', 'aprovechamiento', 'egresados', 'titulados'];
    const NOMBRES = {
        matricula: 'Matrícula', aprovechamiento: 'Aprovechamiento Académico',
        egresados: 'Egresados', titulados: 'Titulados',
    };
    const BADGES = {
        pendiente: { clase: 'vc-badge--pendiente', texto: 'Pendiente' },
        validado: { clase: 'vc-badge--validado', texto: 'Validado' },
        espera: { clase: 'vc-badge--espera', texto: 'En espera' },
        sin_datos: { clase: 'vc-badge--sin', texto: 'Sin información' },
    };

    const ICO_OJO = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    const ICO_OK = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 12.5l5 5L19.5 7"/></svg>';
    const ICO_X = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';

    const el = {
        periodoSel: document.getElementById('vc-periodo-sel'),
        nivel: document.getElementById('vc-nivel'),
        tbody: document.getElementById('vc-tbody'),
        tabla: document.getElementById('vc-tabla-contenedor'),
        vacio: document.getElementById('vc-vacio'),
        refrescar: document.getElementById('vc-refrescar'),
        modalAcuse: document.getElementById('vc-modal-acuse'),
        acuseTitulo: document.getElementById('vc-acuse-titulo'),
        acuseCuerpo: document.getElementById('vc-acuse-cuerpo'),
        acuseDescargar: document.getElementById('vc-acuse-descargar'),
        modalRechazo: document.getElementById('vc-modal-rechazo'),
        rechazoTitulo: document.getElementById('vc-rechazo-titulo'),
        rechazoMotivo: document.getElementById('vc-rechazo-motivo'),
        rechazoContador: document.getElementById('vc-rechazo-contador'),
        rechazoError: document.getElementById('vc-rechazo-error'),
        rechazoConfirmar: document.getElementById('vc-rechazo-confirmar'),
        modalConfirm: document.getElementById('vc-modal-confirm'),
        confirmTitulo: document.getElementById('vc-confirm-titulo'),
        confirmTexto: document.getElementById('vc-confirm-texto'),
        confirmAceptar: document.getElementById('vc-confirm-aceptar'),
        toast: document.getElementById('vc-toast'),
    };

    const estado = {
        periodos: [],
        periodo: null,   // {id, periodo, activo}
        niveles: [],
        nivel: null,     // {id, nombre}
        filas: [],       // [{unidad:{id,sigla,nombre}, modulos:{clave:item}}]
        ocupado: false,
        objectUrl: null,
        rechazo: null,   // {idUnidad, clave}
    };

    // ---- Utilidades ----------------------------------------------------------
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));

    async function getJSON(url) {
        const res = await fetch(url, { headers: { Accept: 'application/json' } });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.success === false) {
            throw new Error(data.detail || data.error || data.message || `Error ${res.status}`);
        }
        return data;
    }

    async function postJSON(url, body) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const txt = await res.text();
        let data = {};
        try { data = JSON.parse(txt); } catch (_) { data = { detail: txt.slice(0, 200) }; }
        if (!res.ok || data.success === false) {
            throw new Error(data.detail || data.error || data.message || `Error ${res.status}`);
        }
        return data;
    }

    function sanitizarError(msg) {
        if (!msg) return 'Ocurrió un error inesperado al procesar la solicitud.';
        let s = String(msg).trim();
        if (s.includes('Traceback (most recent call last)')) {
            const lineas = s.split('\n').map((l) => l.trim()).filter(Boolean);
            s = lineas[lineas.length - 1] || 'Error interno del servidor.';
        }
        if (s.includes('[SQL Server]')) {
            const m = s.match(/\[SQL Server\]([^(\]]+)/);
            if (m && m[1]) s = m[1].trim();
        }
        if (s.length > 200) s = s.substring(0, 197) + '…';
        return s;
    }

    function mostrarToast(texto, tipo) {
        el.toast.textContent = tipo === 'error' ? sanitizarError(texto) : texto;
        el.toast.className = `vc-toast vc-toast--${tipo || 'ok'} vc-toast--visible`;
        clearTimeout(mostrarToast._t);
        mostrarToast._t = setTimeout(() => el.toast.classList.remove('vc-toast--visible'), 6000);
    }

    function abrirModal(m) {
        m.classList.add('vc-modal--abierto');
        document.body.classList.add('vc-sin-scroll');
    }

    function cerrarModal(m) {
        m.classList.remove('vc-modal--abierto');
        if (!document.querySelector('.vc-modal--abierto')) {
            document.body.classList.remove('vc-sin-scroll');
        }
    }

    function buscarUnidad(idUnidad) {
        const fila = estado.filas.find((f) => f.unidad.id === idUnidad);
        return fila ? fila.unidad : null;
    }

    function contexto(unidad) {
        return {
            periodo: estado.periodo.periodo,
            sigla: unidad.sigla,
            nivel: estado.nivel.nombre,
            idUnidad: unidad.id,
            idNivel: estado.nivel.id,
        };
    }

    // ---- Filtros ---------------------------------------------------------------
    function poblarFiltros() {
        el.periodoSel.innerHTML = '<option value="">Seleccione un periodo</option>' +
            estado.periodos.map((p) =>
                `<option value="${p.id}">${esc(p.periodo)}${p.activo ? ' (activo)' : ''}</option>`
            ).join('');
        el.nivel.innerHTML = '<option value="">Seleccione un nivel</option>' +
            estado.niveles.map((n) => `<option value="${n.id}">${esc(n.nombre)}</option>`).join('');

        // El periodo activo viene preseleccionado
        const activo = estado.periodos.find((p) => p.activo);
        if (activo) {
            el.periodoSel.value = String(activo.id);
            estado.periodo = activo;
        }
    }

    function limpiarTabla() {
        liberarAcuse();
        cerrarRechazo();
        estado.filas = [];
        el.tbody.innerHTML = '';
        el.tabla.style.display = 'none';
        el.vacio.style.display = '';
        el.refrescar.disabled = true;
    }

    function filtrosCompletos() {
        return Boolean(estado.periodo && estado.nivel);
    }

    // ---- Tabla -------------------------------------------------------------------
    function celdaModulo(fila, clave) {
        const m = fila.modulos[clave];
        const badge = BADGES[m.estado] || BADGES.sin_datos;
        const turno = m.puede_validar ? '' : 'disabled';
        const motivo = m.estado === 'espera' && m.esperando_por
            ? `Esperando a: ${m.esperando_por}`
            : (m.estado === 'validado' ? 'Ya validado por tu rol' : 'No es tu turno de validación');
        const tituloTurno = m.puede_validar ? '' : `title="${esc(motivo)}"`;
        const verDeshab = m.estado === 'sin_datos' ? 'disabled' : '';
        const detalle = m.estado === 'espera' && m.esperando_por
            ? `<span class="vc-celda__detalle">Esperando a ${esc(m.esperando_por)}</span>` : '';
        return `
        <td class="vc-celda" data-ua="${fila.unidad.id}" data-modulo="${clave}">
            <span class="vc-badge ${badge.clase}">${badge.texto}</span>
            ${detalle}
            <div class="vc-celda__acciones">
                <button type="button" class="vc-btn vc-btn--mini vc-btn--ver" data-accion="ver" ${verDeshab}
                    title="Visualizar acuse" aria-label="Visualizar acuse de ${esc(NOMBRES[clave])} de ${esc(fila.unidad.sigla)}">${ICO_OJO}</button>
                <button type="button" class="vc-btn vc-btn--mini vc-btn--validar" data-accion="validar" ${turno}
                    title="${m.puede_validar ? 'Validar' : esc(motivo)}"
                    aria-label="Validar ${esc(NOMBRES[clave])} de ${esc(fila.unidad.sigla)}">${ICO_OK}</button>
                <button type="button" class="vc-btn vc-btn--mini vc-btn--rechazar" data-accion="rechazar" ${turno}
                    title="${m.puede_validar ? 'Rechazar' : esc(motivo)}"
                    aria-label="Rechazar ${esc(NOMBRES[clave])} de ${esc(fila.unidad.sigla)}">${ICO_X}</button>
            </div>
        </td>`;
    }

    function renderTabla() {
        el.vacio.style.display = 'none';
        el.refrescar.disabled = false;

        if (!estado.filas.length) {
            el.tabla.style.display = 'none';
            el.vacio.style.display = '';
            el.vacio.textContent = 'No hay Unidades Académicas para el nivel seleccionado.';
            return;
        }

        el.tbody.innerHTML = estado.filas.map((f) => `
            <tr class="vc-tr">
                <th scope="row" class="vc-td-ua">
                    <span class="vc-ua__sigla">${esc(f.unidad.sigla)}</span>
                    <span class="vc-ua__nombre">${esc(f.unidad.nombre)}</span>
                </th>
                ${CLAVES.map((c) => celdaModulo(f, c)).join('')}
            </tr>`).join('');
        el.tabla.style.display = '';
    }

    async function cargarTabla(silencioso) {
        if (!filtrosCompletos()) return;
        if (!silencioso) {
            el.vacio.style.display = 'none';
            el.tabla.style.display = 'none';
            el.tbody.innerHTML = '';
            el.vacio.textContent = '';
            el.vacio.insertAdjacentHTML('afterbegin', '<span class="vc-spinner"></span> Consultando Unidades Académicas…');
            el.vacio.style.display = '';
        }
        try {
            const data = await getJSON(`/validacion/tabla?id_periodo=${estado.periodo.id}&id_nivel=${estado.nivel.id}`);
            estado.filas = data.filas || [];
            renderTabla();
        } catch (err) {
            el.tabla.style.display = 'none';
            el.vacio.style.display = '';
            el.vacio.innerHTML = `<span class="vc-error">No se pudo consultar el estado: ${esc(err.message)}</span>`;
        }
    }

    // ---- Acuse en burbuja emergente ----------------------------------------
    function liberarAcuse() {
        if (estado.objectUrl) {
            URL.revokeObjectURL(estado.objectUrl);
            estado.objectUrl = null;
        }
        el.acuseCuerpo.innerHTML = '';
        el.acuseDescargar.removeAttribute('href');
    }

    async function verAcuse(idUnidad, clave) {
        const unidad = buscarUnidad(idUnidad);
        if (!unidad) return;
        const c = contexto(unidad);

        liberarAcuse();
        el.acuseTitulo.textContent = `Acuse de ${NOMBRES[clave]} — ${unidad.sigla} · ${c.nivel} · ${c.periodo}`;
        el.acuseCuerpo.innerHTML = '<div class="vc-cargando vc-cargando--grande"><span class="vc-spinner"></span> Generando acuse…</div>';
        abrirModal(el.modalAcuse);

        const url = `/${clave}/acuse-validacion/pdf?periodo=${encodeURIComponent(c.periodo)}` +
            `&nivel=${encodeURIComponent(c.nivel)}&unidad=${encodeURIComponent(c.sigla)}`;

        try {
            const res = await fetch(url);
            if (!res.ok) {
                let detalle = '';
                try { const j = await res.json(); detalle = j.detail || j.error || ''; } catch (_) { /* html/texto */ }
                throw new Error(detalle || `Error ${res.status} al generar el PDF`);
            }
            const tipo = res.headers.get('content-type') || '';
            if (!tipo.includes('pdf')) throw new Error('El servidor no devolvió un PDF.');
            const blob = await res.blob();
            if (!el.modalAcuse.classList.contains('vc-modal--abierto')) return;

            estado.objectUrl = URL.createObjectURL(blob);
            el.acuseCuerpo.innerHTML = '';
            const frame = document.createElement('iframe');
            frame.className = 'vc-acuse-frame';
            frame.title = `Acuse de ${NOMBRES[clave]}`;
            frame.src = estado.objectUrl;
            el.acuseCuerpo.appendChild(frame);

            el.acuseDescargar.href = estado.objectUrl;
            el.acuseDescargar.download = `Acuse_${clave}_${c.sigla}_${c.periodo}.pdf`.replace(/[\s/]+/g, '_');
        } catch (err) {
            el.acuseCuerpo.innerHTML = `<div class="vc-error">No se pudo mostrar el acuse: ${esc(err.message)}</div>`;
        }
    }

    function cerrarAcuse() {
        cerrarModal(el.modalAcuse);
        liberarAcuse();
    }

    // ---- Validar -------------------------------------------------------------
    function confirmar(titulo, textoHtml, textoBoton) {
        return new Promise((resolve) => {
            el.confirmTitulo.textContent = titulo;
            el.confirmTexto.innerHTML = textoHtml;
            el.confirmAceptar.textContent = textoBoton;
            abrirModal(el.modalConfirm);

            const limpiar = (valor) => {
                el.confirmAceptar.removeEventListener('click', aceptar);
                el.modalConfirm.querySelectorAll('[data-cerrar]').forEach((b) => b.removeEventListener('click', cancelar));
                cerrarModal(el.modalConfirm);
                resolve(valor);
            };
            const aceptar = () => limpiar(true);
            const cancelar = () => limpiar(false);
            el.confirmAceptar.addEventListener('click', aceptar);
            el.modalConfirm.querySelectorAll('[data-cerrar]').forEach((b) => b.addEventListener('click', cancelar));
        });
    }

    function resumenHtml(unidad, clave) {
        return `Módulo: <b>${esc(NOMBRES[clave])}</b><br>Periodo: <b>${esc(estado.periodo.periodo)}</b><br>` +
            `Nivel: <b>${esc(estado.nivel.nombre)}</b><br>Unidad: <b>${esc(unidad.sigla)}</b>`;
    }

    function moduloDe(idUnidad, clave) {
        const fila = estado.filas.find((f) => f.unidad.id === idUnidad);
        return fila ? fila.modulos[clave] : null;
    }

    async function validar(idUnidad, clave) {
        const unidad = buscarUnidad(idUnidad);
        const mod = moduloDe(idUnidad, clave);
        if (!unidad || !mod || !mod.puede_validar || estado.ocupado) return;

        const ok = await confirmar(
            `¿Validar ${NOMBRES[clave]}?`,
            `${resumenHtml(unidad, clave)}<br><br>Esta acción registrará tu validación y bloqueará cualquier modificación futura.`,
            'Sí, validar'
        );
        if (!ok) return;

        await ejecutar(unidad, clave, 'validar', null);
    }

    // ---- Rechazar (conserva el cuadro de descripción del rechazo) ------------
    function actualizarContador() {
        el.rechazoContador.textContent = String(el.rechazoMotivo.value.length);
    }

    function abrirRechazo(idUnidad, clave) {
        const unidad = buscarUnidad(idUnidad);
        const mod = moduloDe(idUnidad, clave);
        if (!unidad || !mod || !mod.puede_validar || estado.ocupado) return;

        estado.rechazo = { idUnidad, clave };
        el.rechazoTitulo.textContent = `Rechazar ${NOMBRES[clave]} — ${unidad.sigla}`;
        el.rechazoMotivo.value = '';
        el.rechazoError.textContent = '';
        el.rechazoConfirmar.disabled = false;
        actualizarContador();
        abrirModal(el.modalRechazo);
        setTimeout(() => el.rechazoMotivo.focus(), 60);
    }

    function cerrarRechazo() {
        cerrarModal(el.modalRechazo);
        estado.rechazo = null;
    }

    async function confirmarRechazo() {
        if (!estado.rechazo) return;
        const { idUnidad, clave } = estado.rechazo;
        const unidad = buscarUnidad(idUnidad);
        if (!unidad) return;

        const motivo = el.rechazoMotivo.value.trim();
        if (motivo.length < 10) {
            el.rechazoError.textContent = 'Ingrese un motivo de rechazo de al menos 10 caracteres.';
            el.rechazoMotivo.focus();
            return;
        }

        const ok = await confirmar(
            `¿Rechazar ${NOMBRES[clave]}?`,
            `${resumenHtml(unidad, clave)}<br><br><b>Motivo:</b> ${esc(motivo.substring(0, 100))}${motivo.length > 100 ? '…' : ''}` +
            '<br><br>Esta acción devolverá la información para correcciones.',
            'Sí, rechazar'
        );
        if (!ok) return;

        el.rechazoConfirmar.disabled = true;
        const res = await ejecutar(unidad, clave, 'rechazar', motivo);
        if (res.exito) {
            cerrarRechazo();
        } else {
            el.rechazoConfirmar.disabled = false;
            el.rechazoError.textContent = res.error || 'No se pudo rechazar el módulo.';
        }
    }

    // ---- Ejecución común (mismos endpoints/SPs de siempre) ------------------
    async function ejecutar(unidad, clave, tipo, motivo) {
        const cfg = ACCIONES[clave];
        const nombre = NOMBRES[clave];
        const cuerpo = cfg.payload(contexto(unidad));
        if (tipo === 'rechazar') cuerpo.motivo = motivo;

        estado.ocupado = true;
        root.classList.add('vc-ocupado');
        mostrarToast(tipo === 'validar'
            ? `Validando ${nombre} de ${unidad.sigla}…`
            : `Enviando rechazo de ${nombre} de ${unidad.sigla}…`, 'info');

        try {
            const data = await postJSON(cfg[tipo], cuerpo);
            const msg = data.mensaje || data.message || data.detail ||
                (tipo === 'validar' ? `${nombre} validado correctamente.` : `${nombre} rechazado correctamente.`);
            mostrarToast(msg, 'ok');
            await cargarTabla(true);
            return { exito: true };
        } catch (err) {
            const errLimpio = sanitizarError(err.message);
            mostrarToast(`${tipo === 'validar' ? 'No se pudo validar' : 'No se pudo rechazar'}: ${errLimpio}`, 'error');
            return { exito: false, error: errLimpio };
        } finally {
            estado.ocupado = false;
            root.classList.remove('vc-ocupado');
        }
    }

    // ---- Eventos ------------------------------------------------------------
    function alCambiarFiltros() {
        const idP = Number(el.periodoSel.value);
        const idN = Number(el.nivel.value);
        estado.periodo = estado.periodos.find((p) => p.id === idP) || null;
        estado.nivel = estado.niveles.find((n) => n.id === idN) || null;
        if (filtrosCompletos()) {
            cargarTabla(false);
        } else {
            limpiarTabla();
            el.vacio.textContent = 'Elija un periodo y un nivel para ver el estado de Matrícula, Aprovechamiento, Egresados y Titulados de cada Unidad Académica.';
        }
    }

    el.periodoSel.addEventListener('change', alCambiarFiltros);
    el.nivel.addEventListener('change', alCambiarFiltros);
    el.refrescar.addEventListener('click', () => cargarTabla(false));

    el.tbody.addEventListener('click', (ev) => {
        const btn = ev.target.closest('button[data-accion]');
        if (!btn || btn.disabled) return;
        const celda = btn.closest('.vc-celda');
        const idUnidad = Number(celda.dataset.ua);
        const clave = celda.dataset.modulo;
        const accion = btn.dataset.accion;
        if (accion === 'ver') verAcuse(idUnidad, clave);
        else if (accion === 'validar') validar(idUnidad, clave);
        else if (accion === 'rechazar') abrirRechazo(idUnidad, clave);
    });

    el.modalAcuse.querySelectorAll('[data-cerrar]').forEach((b) => b.addEventListener('click', cerrarAcuse));
    el.modalRechazo.querySelectorAll('[data-cerrar]').forEach((b) => b.addEventListener('click', cerrarRechazo));
    el.rechazoMotivo.addEventListener('input', () => {
        actualizarContador();
        if (el.rechazoMotivo.value.trim().length >= 10) el.rechazoError.textContent = '';
    });
    el.rechazoConfirmar.addEventListener('click', confirmarRechazo);

    document.addEventListener('keydown', (ev) => {
        if (ev.key !== 'Escape') return;
        if (el.modalConfirm.classList.contains('vc-modal--abierto')) {
            el.modalConfirm.querySelector('[data-cerrar]').click();
        } else if (el.modalRechazo.classList.contains('vc-modal--abierto')) {
            cerrarRechazo();
        } else if (el.modalAcuse.classList.contains('vc-modal--abierto')) {
            cerrarAcuse();
        }
    });

    // ---- Inicio -------------------------------------------------------------
    (async function init() {
        try {
            const data = await getJSON('/validacion/catalogo');
            estado.periodos = data.periodos || [];
            estado.niveles = data.niveles || [];
            poblarFiltros();
        } catch (err) {
            el.periodoSel.disabled = true;
            el.nivel.disabled = true;
            el.vacio.style.display = '';
            el.vacio.innerHTML = `<span class="vc-error">${esc(err.message)}</span>`;
        }
    })();
})();
