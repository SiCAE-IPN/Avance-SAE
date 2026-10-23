// Catálogo de Programas (pestaña dentro de Catálogos > Usuarios)
// Alta, modificación (Nivel/Rama/Semestre) y baja lógica mediante /catalogo_programas/*.
// El nombre del programa es su identificador en los SP, por lo que no es editable.

function initProgramasCatalogo() {
    const panelProgramas = document.getElementById('tab-programas');
    if (!panelProgramas) return;

    // ---------- Pestañas ----------
    const tabs = document.querySelectorAll('.catalogo-tab');
    let programasCargados = false;

    async function cargarDatosPestaña() {
        if (programasCargados) return;
        programasCargados = true;
        await cargarOpciones();
        await cargarProgramas();
    }

    function activarTab(idPanel) {
        tabs.forEach(t => {
            const activa = t.dataset.tab === idPanel;
            t.classList.toggle('active', activa);
            t.setAttribute('aria-selected', activa ? 'true' : 'false');
        });
        document.querySelectorAll('.catalogo-tab-panel').forEach(p => {
            const activo = p.id === idPanel;
            p.classList.toggle('active', activo);
            p.hidden = !activo;
        });
        if (idPanel === 'tab-programas') {
            cargarDatosPestaña();
        }
        history.replaceState(null, '', idPanel === 'tab-programas' ? '#programas' : window.location.pathname + window.location.search);
    }

    tabs.forEach(t => t.addEventListener('click', () => activarTab(t.dataset.tab)));
    if (window.location.hash && window.location.hash.includes('programas')) {
        activarTab('tab-programas');
    }

    // ---------- Elementos ----------
    const form = document.getElementById('prog-form');
    const inNombre = document.getElementById('prog-nombre');
    const selNivel = document.getElementById('prog-nivel');
    const selRama = document.getElementById('prog-rama');
    const selSemestre = document.getElementById('prog-semestre');
    const selUnidad = document.getElementById('prog-unidad');
    const selModalidad = document.getElementById('prog-modalidad');
    const btnGuardar = document.getElementById('prog-btn-guardar');
    const btnLimpiar = document.getElementById('prog-btn-limpiar');
    const btnEliminar = document.getElementById('prog-btn-eliminar');
    const titulo = document.getElementById('prog-titulo');
    const mensaje = document.getElementById('prog-mensaje');
    const tbody = document.getElementById('prog-tbody');
    const filtroTexto = document.getElementById('prog-filtro-texto');
    const filtroUnidad = document.getElementById('prog-filtro-unidad');
    const filtroNivel = document.getElementById('prog-filtro-nivel');
    const filtroModalidad = document.getElementById('prog-filtro-modalidad');
    const filtroEstatus = document.getElementById('prog-filtro-estatus');
    const btnLimpiarFiltros = document.getElementById('prog-btn-limpiar-filtros');
    const modal = document.getElementById('prog-modal-baja');
    const modalNombre = document.getElementById('prog-modal-nombre');
    const modalConfirmar = document.getElementById('prog-modal-confirmar');
    const modalCancelar = document.getElementById('prog-modal-cancelar');

    let programas = [];
    let seleccionado = null; // programa seleccionado en la tabla (modo consulta/baja)

    function esc(valor) {
        return String(valor ?? '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function mostrarMensaje(texto, tipo) {
        const color = tipo === 'ok' ? '#28a745' : tipo === 'info' ? '#007bff' : '#dc3545';
        const icono = tipo === 'ok' ? '✅' : tipo === 'info' ? '⏳' : '❌';
        mensaje.innerHTML = `<p style="color:${color}; word-break:break-word;">${icono} ${esc(texto)}</p>`;
    }

    function esBaja(p) {
        const est = String(p.estatus || '').toLowerCase().trim();
        return est === 'inactivo' || est === 'eliminado' || est.includes('baja') || est.includes('inactiv');
    }

    // ---------- Carga de datos ----------
    function llenarSelect(select, opciones, vacio) {
        if (!select) return;
        select.innerHTML = `<option value="">${esc(vacio)}</option>` +
            opciones.map(o => `<option value="${esc(o.valor)}">${esc(o.etiqueta)}</option>`).join('');
    }

    async function cargarOpciones() {
        try {
            const resp = await fetch('/catalogo_programas/opciones', {
                credentials: 'same-origin',
                cache: 'no-store'
            });
            if (resp.status === 401) {
                console.warn('[programas] No autenticado en /opciones');
                return false;
            }
            if (!resp.ok) throw new Error();
            const data = await resp.json();

            llenarSelect(selNivel, data.niveles || [], '-- Seleccione un Nivel --');
            llenarSelect(selRama, data.ramas || [], '-- Seleccione una Rama --');
            llenarSelect(selSemestre, data.semestres || [], '-- Seleccione un Semestre --');
            llenarSelect(selUnidad, data.unidades || [], '-- Seleccione una Unidad Académica --');
            llenarSelect(selModalidad, data.modalidades || [], '-- Seleccione una Modalidad --');

            // Filtros de la tabla
            llenarSelect(filtroUnidad, data.unidades || [], 'Todas las Unidades');
            llenarSelect(filtroNivel, data.niveles || [], 'Todos los niveles');
            llenarSelect(filtroModalidad, data.modalidades || [], 'Todas las modalidades');

            // Dejar el formulario vacío y los filtros en "Todas"
            if (selUnidad) selUnidad.value = '';
            if (selNivel) selNivel.value = '';
            if (selRama) selRama.value = '';
            if (selSemestre) selSemestre.value = '';
            if (selModalidad) selModalidad.value = '';
            if (filtroUnidad) filtroUnidad.value = '';
            if (filtroNivel) filtroNivel.value = '';
            if (filtroModalidad) filtroModalidad.value = '';

            return true;
        } catch (e) {
            mostrarMensaje('No se pudieron cargar las opciones del formulario.', 'error');
            return false;
        }
    }

    async function cargarProgramas(reintentos = 2) {
        tbody.innerHTML = '<tr><td colspan="7" class="prog-vacio">Cargando programas…</td></tr>';
        try {
            const params = new URLSearchParams();
            const u = filtroUnidad ? filtroUnidad.value.trim() : '';
            const n = filtroNivel ? filtroNivel.value.trim() : '';
            if (u) params.set('unidad', u);
            if (n) params.set('nivel', n);

            const url = '/catalogo_programas/datos' + (params.toString() ? '?' + params.toString() : '');
            const resp = await fetch(url, {
                credentials: 'same-origin',
                cache: 'no-store'
            });

            if (resp.status === 401) {
                if (reintentos > 0) {
                    await new Promise(r => setTimeout(r, 600));
                    return await cargarProgramas(reintentos - 1);
                }
                programasCargados = false;
                tbody.innerHTML = '<tr><td colspan="7" class="prog-vacio" style="color:#dc3545;">Sesión no válida o expirada. <a href="/login" style="color:#750946; font-weight:bold; text-decoration:underline;">Iniciar sesión</a></td></tr>';
                return;
            }

            const data = await resp.json();
            if (!resp.ok) throw new Error(data.mensaje || data.detail || 'Error al consultar programas');
            programas = data.programas || [];
            const estatus = [...new Set(programas.map(p => p.estatus).filter(Boolean))].sort();
            const estatusPrevio = filtroEstatus ? filtroEstatus.value : '';
            filtroEstatus.innerHTML = '<option value="">Todos los estatus</option>' +
                estatus.map(e => `<option value="${esc(e)}">${esc(e)}</option>`).join('');
            if (filtroEstatus && estatusPrevio && estatus.includes(estatusPrevio)) {
                filtroEstatus.value = estatusPrevio;
            }
            pintarTabla();
        } catch (e) {
            if (reintentos > 0) {
                await new Promise(r => setTimeout(r, 600));
                return await cargarProgramas(reintentos - 1);
            }
            programasCargados = false;
            tbody.innerHTML = `<tr><td colspan="7" class="prog-vacio" style="color:#dc3545;">
                ${esc(e.message || 'Error al consultar programas')}
                <br><button type="button" id="btn-reint-prog" class="btn-filtros" style="margin-top:8px; padding:4px 12px; cursor:pointer;">Reintentar</button>
            </td></tr>`;
            const btnR = document.getElementById('btn-reint-prog');
            if (btnR) btnR.addEventListener('click', () => { cargarProgramas(1); });
        }
    }

    window.recargarProgramasCatalogo = function () {
        programasCargados = false;
        cargarDatosPestaña();
    };

    // ---------- Tabla ----------
    function pintarTabla() {
        const texto = filtroTexto.value.trim().toLowerCase();
        const est = filtroEstatus.value;
        const mod = filtroModalidad ? filtroModalidad.value : '';

        const filtrados = programas.filter(p => {
            const coincideTexto = !texto || [p.unidad, p.nombre, p.nivel, p.rama, p.semestre, p.modalidad]
                .some(v => String(v ?? '').toLowerCase().includes(texto));
            const coincideModalidad = !mod || p.modalidad === mod;
            const coincideEstatus = !est || p.estatus === est;
            return coincideTexto && coincideModalidad && coincideEstatus;
        });

        if (!filtrados.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="prog-vacio">Sin programas para mostrar.</td></tr>';
            return;
        }

        tbody.innerHTML = filtrados.map(p => `
            <tr class="fila-edit ${esBaja(p) ? 'prog-fila-baja' : ''} ${seleccionado && seleccionado.nombre === p.nombre && (seleccionado.unidad || '') === (p.unidad || '') ? 'prog-fila-seleccionada' : ''}"
                data-nombre="${esc(p.nombre)}"
                data-unidad="${esc(p.unidad || '')}"
                data-modalidad="${esc(p.modalidad || '')}">
                <td>${esc(p.unidad || '-')}</td>
                <td>${esc(p.nombre)}</td>
                <td>${esc(p.modalidad || '-')}</td>
                <td>${esc(p.nivel || '-')}</td>
                <td>${esc(p.rama || '-')}</td>
                <td>${esc(p.semestre || '-')}</td>
                <td>${esc(p.estatus || '-')}</td>
            </tr>`).join('');
    }

    tbody.addEventListener('click', function (e) {
        const fila = e.target.closest('tr[data-nombre]');
        if (!fila) return;
        const nombre = fila.dataset.nombre;
        const unidad = fila.dataset.unidad || '';
        const modalidad = fila.dataset.modalidad || '';
        const p = programas.find(x => x.nombre === nombre && (x.unidad || '') === unidad && (x.modalidad || '') === modalidad)
            || programas.find(x => x.nombre === nombre);
        if (p) seleccionarPrograma(p);
    });

    // ---------- Modo formulario ----------
    function bloquearCampos(bloquear, soloCamposModificables = false) {
        inNombre.disabled = bloquear || soloCamposModificables;
        if (selUnidad) selUnidad.disabled = bloquear || soloCamposModificables;
        if (selModalidad) selModalidad.disabled = bloquear || soloCamposModificables;
        [selNivel, selRama, selSemestre].forEach(c => { if (c) c.disabled = bloquear; });
    }

    function modoRegistro() {
        seleccionado = null;
        form.reset();
        bloquearCampos(false);
        if (selUnidad) selUnidad.value = '';
        if (selNivel) selNivel.value = '';
        if (selRama) selRama.value = '';
        if (selSemestre) selSemestre.value = '';
        if (selModalidad) selModalidad.value = '';
        btnGuardar.disabled = false;
        btnGuardar.style.display = '';
        btnGuardar.textContent = 'Registrar';
        btnEliminar.disabled = true;
        btnEliminar.style.display = 'none';
        titulo.textContent = 'Registro Programa';
        pintarTabla();
    }

    function seleccionarPrograma(p) {
        seleccionado = p;
        mensaje.innerHTML = '';
        inNombre.value = p.nombre || '';
        // Combos con opciones
        [[selNivel, p.nivel], [selRama, p.rama], [selSemestre, p.semestre], [selUnidad, p.unidad], [selModalidad, p.modalidad]].forEach(([sel, etiqueta]) => {
            if (!sel) return;
            const opt = Array.from(sel.options).find(o => o.value === String(etiqueta ?? '').trim() || o.textContent.trim() === String(etiqueta ?? '').trim());
            sel.value = opt ? opt.value : '';
        });

        if (esBaja(p)) {
            // Programa inactivo / dado de baja: solo consulta, sin opciones de modificar ni dar de baja
            bloquearCampos(true);
            btnGuardar.disabled = true;
            btnGuardar.style.display = 'none';
            btnEliminar.disabled = true;
            btnEliminar.style.display = 'none';
            titulo.textContent = 'Programa inactivo';
            mostrarMensaje(`El programa '${p.nombre}' se encuentra inactivo y no puede ser modificado ni dado de baja.`, 'info');
        } else {
            // Edición: Nivel, Rama y Semestre editables. Nombre, UA y Modalidad fijos.
            bloquearCampos(false, true);
            btnGuardar.disabled = false;
            btnGuardar.style.display = '';
            btnGuardar.textContent = 'Actualizar';
            btnEliminar.disabled = false;
            btnEliminar.style.display = 'inline-block';
            titulo.textContent = 'Editar Programa';
        }
        pintarTabla();
    }

    btnLimpiar.addEventListener('click', function () {
        mensaje.innerHTML = '';
        modoRegistro();
    });

    // ---------- Alta / Modificación ----------
    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        const editando = !!seleccionado;
        if (editando && esBaja(seleccionado)) return;

        let payload;
        if (editando) {
            payload = {
                nombre: seleccionado.nombre,
                nivel: selNivel.value,
                rama: selRama.value,
                semestre: selSemestre.value,
            };
            if (!payload.nombre || !payload.nivel || !payload.rama || !payload.semestre) {
                mostrarMensaje('Completa Nombre, Nivel, Rama y Semestre.', 'error');
                return;
            }
        } else {
            payload = {
                nombre: inNombre.value.trim(),
                nivel: selNivel.value,
                rama: selRama.value,
                semestre: selSemestre.value,
                unidad: selUnidad ? selUnidad.value : '',
                modalidad: selModalidad ? selModalidad.value : '',
            };
            if (!payload.nombre || !payload.nivel || !payload.rama || !payload.semestre || !payload.unidad || !payload.modalidad) {
                mostrarMensaje('Completa Nombre, Nivel, Rama, Semestre, Unidad Académica y Modalidad.', 'error');
                return;
            }
        }

        btnGuardar.disabled = true;
        mostrarMensaje(editando ? 'Actualizando programa...' : 'Registrando programa...', 'info');
        try {
            const resp = await fetch(editando ? '/catalogo_programas/modificar' : '/catalogo_programas/alta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(payload),
            });
            const data = await resp.json().catch(() => ({}));
            if (resp.ok && data.status === 'ok') {
                if (!editando) {
                    if (filtroTexto) filtroTexto.value = '';
                    if (filtroEstatus) filtroEstatus.value = '';
                }
                modoRegistro();
                mostrarMensaje(data.mensaje || (editando ? 'Programa modificado correctamente.' : 'Programa registrado correctamente.'), 'ok');
                await cargarProgramas();
            } else if (!editando && data.status === 'warning') {
                if (filtroTexto) filtroTexto.value = '';
                if (filtroEstatus) filtroEstatus.value = '';
                modoRegistro();
                mostrarMensaje(data.mensaje, 'error');
                await cargarProgramas();
            } else {
                mostrarMensaje(data.mensaje || data.detail || (editando ? 'No se pudo modificar el programa.' : 'No se pudo registrar el programa.'), 'error');
            }
        } catch (err) {
            mostrarMensaje('Error de conexión: ' + err.message, 'error');
        } finally {
            btnGuardar.disabled = false;
            if (typeof window.forceHideLoadingBanner === 'function') {
                window.forceHideLoadingBanner();
            }
        }
    });

    // ---------- Baja ----------
    btnEliminar.addEventListener('click', function () {
        if (!seleccionado || esBaja(seleccionado)) return;
        modalNombre.textContent = seleccionado.nombre;
        modal.classList.add('show');
    });

    modalCancelar.addEventListener('click', e => { e.preventDefault(); modal.classList.remove('show'); });
    modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });

    modalConfirmar.addEventListener('click', async function () {
        modal.classList.remove('show');
        if (!seleccionado || esBaja(seleccionado)) return;
        const nombre = seleccionado.nombre;
        mostrarMensaje('Dando de baja el programa...', 'info');
        try {
            const resp = await fetch('/catalogo_programas/baja', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ nombre }),
            });
            const data = await resp.json().catch(() => ({}));
            if (resp.ok && data.status === 'ok') {
                modoRegistro();
                mostrarMensaje(data.mensaje || 'Programa dado de baja correctamente.', 'ok');
            } else {
                mostrarMensaje(data.mensaje || data.detail || 'No se pudo dar de baja el programa.', 'error');
            }
            await cargarProgramas();
        } catch (err) {
            mostrarMensaje('Error de conexión: ' + err.message, 'error');
            await cargarProgramas();
        } finally {
            if (typeof window.forceHideLoadingBanner === 'function') {
                window.forceHideLoadingBanner();
            }
        }
    });

    // ---------- Filtros ----------
    filtroTexto.addEventListener('input', pintarTabla);
    filtroEstatus.addEventListener('change', pintarTabla);
    if (filtroModalidad) filtroModalidad.addEventListener('change', pintarTabla);
    if (filtroUnidad) filtroUnidad.addEventListener('change', () => cargarProgramas());
    if (filtroNivel) filtroNivel.addEventListener('change', () => cargarProgramas());

    btnLimpiarFiltros.addEventListener('click', function () {
        filtroTexto.value = '';
        filtroEstatus.value = '';
        if (filtroModalidad) filtroModalidad.value = '';
        if (filtroUnidad) filtroUnidad.value = '';
        if (filtroNivel) filtroNivel.value = '';
        cargarProgramas();
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProgramasCatalogo);
} else {
    initProgramasCatalogo();
}
