// Catálogo de Programas (pestaña dentro de Catálogos > Usuarios)
// Alta, modificación (Nivel/Rama/Semestre) y baja lógica mediante /catalogo_programas/*.
// El nombre del programa es su identificador en los SP, por lo que no es editable.

document.addEventListener('DOMContentLoaded', function () {
    const panelProgramas = document.getElementById('tab-programas');
    if (!panelProgramas) return;

    // ---------- Pestañas ----------
    const tabs = document.querySelectorAll('.catalogo-tab');
    let programasCargados = false;

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
        if (idPanel === 'tab-programas' && !programasCargados) {
            programasCargados = true;
            cargarOpciones();
            cargarProgramas();
        }
        history.replaceState(null, '', idPanel === 'tab-programas' ? '#programas' : window.location.pathname + window.location.search);
    }

    tabs.forEach(t => t.addEventListener('click', () => activarTab(t.dataset.tab)));
    if (window.location.hash === '#programas') activarTab('tab-programas');

    // ---------- Elementos ----------
    const form = document.getElementById('prog-form');
    const inNombre = document.getElementById('prog-nombre');
    const selNivel = document.getElementById('prog-nivel');
    const selRama = document.getElementById('prog-rama');
    const selSemestre = document.getElementById('prog-semestre');
    const btnGuardar = document.getElementById('prog-btn-guardar');
    const btnLimpiar = document.getElementById('prog-btn-limpiar');
    const btnEliminar = document.getElementById('prog-btn-eliminar');
    const titulo = document.getElementById('prog-titulo');
    const mensaje = document.getElementById('prog-mensaje');
    const tbody = document.getElementById('prog-tbody');
    const filtroTexto = document.getElementById('prog-filtro-texto');
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
        mensaje.innerHTML = `<p style="color:${color};">${icono} ${esc(texto)}</p>`;
    }

    function esBaja(p) {
        return String(p.estatus || '').toLowerCase().includes('baja');
    }

    // ---------- Carga de datos ----------
    function llenarSelect(select, opciones, vacio) {
        select.innerHTML = `<option value="">${esc(vacio)}</option>` +
            opciones.map(o => `<option value="${esc(o.valor)}">${esc(o.etiqueta)}</option>`).join('');
    }

    async function cargarOpciones() {
        try {
            const resp = await fetch('/catalogo_programas/opciones');
            if (!resp.ok) throw new Error();
            const data = await resp.json();
            llenarSelect(selNivel, data.niveles || [], '-- Seleccione un Nivel --');
            llenarSelect(selRama, data.ramas || [], '-- Seleccione una Rama --');
            llenarSelect(selSemestre, data.semestres || [], '-- Seleccione un Semestre --');
        } catch (e) {
            mostrarMensaje('No se pudieron cargar las opciones del formulario.', 'error');
        }
    }

    async function cargarProgramas() {
        tbody.innerHTML = '<tr><td colspan="5" class="prog-vacio">Cargando programas…</td></tr>';
        try {
            const resp = await fetch('/catalogo_programas/datos');
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.mensaje || 'Error al consultar programas');
            programas = data.programas || [];
            const estatus = [...new Set(programas.map(p => p.estatus).filter(Boolean))].sort();
            filtroEstatus.innerHTML = '<option value="">Todos los estatus</option>' +
                estatus.map(e => `<option value="${esc(e)}">${esc(e)}</option>`).join('');
            pintarTabla();
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="5" class="prog-vacio">${esc(e.message || 'Error al consultar programas')}</td></tr>`;
        }
    }

    // ---------- Tabla ----------
    function pintarTabla() {
        const texto = filtroTexto.value.trim().toLowerCase();
        const est = filtroEstatus.value;
        const filtrados = programas.filter(p => {
            const coincideTexto = !texto || [p.nombre, p.nivel, p.rama, p.semestre]
                .some(v => String(v ?? '').toLowerCase().includes(texto));
            return coincideTexto && (!est || p.estatus === est);
        });

        if (!filtrados.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="prog-vacio">Sin programas para mostrar.</td></tr>';
            return;
        }

        tbody.innerHTML = filtrados.map(p => `
            <tr class="fila-edit ${esBaja(p) ? 'prog-fila-baja' : ''} ${seleccionado && seleccionado.nombre === p.nombre ? 'prog-fila-seleccionada' : ''}"
                data-nombre="${esc(p.nombre)}">
                <td>${esc(p.nombre)}</td>
                <td>${esc(p.nivel)}</td>
                <td>${esc(p.rama)}</td>
                <td>${esc(p.semestre)}</td>
                <td>${esc(p.estatus)}</td>
            </tr>`).join('');
    }

    tbody.addEventListener('click', function (e) {
        const fila = e.target.closest('tr[data-nombre]');
        if (!fila) return;
        const p = programas.find(x => x.nombre === fila.dataset.nombre);
        if (p) seleccionarPrograma(p);
    });

    // ---------- Modo formulario ----------
    function bloquearCampos(bloquear, soloNombre = false) {
        inNombre.disabled = bloquear || soloNombre;
        [selNivel, selRama, selSemestre].forEach(c => { c.disabled = bloquear; });
    }

    function modoRegistro() {
        seleccionado = null;
        form.reset();
        bloquearCampos(false);
        btnGuardar.style.display = '';
        btnGuardar.textContent = 'Registrar';
        btnEliminar.style.display = 'none';
        titulo.textContent = 'Registro Programa';
        pintarTabla();
    }

    function seleccionarPrograma(p) {
        seleccionado = p;
        mensaje.innerHTML = '';
        inNombre.value = p.nombre || '';
        // Los combos usan valor = texto (nivel/rama) o Id (semestre): se selecciona por etiqueta.
        [[selNivel, p.nivel], [selRama, p.rama], [selSemestre, p.semestre]].forEach(([sel, etiqueta]) => {
            const opt = Array.from(sel.options).find(o => o.textContent.trim() === String(etiqueta ?? '').trim());
            sel.value = opt ? opt.value : '';
        });
        if (esBaja(p)) {
            // Programa dado de baja: solo consulta
            bloquearCampos(true);
            btnGuardar.style.display = 'none';
            btnEliminar.style.display = 'none';
            titulo.textContent = 'Programa dado de baja';
        } else {
            // Edición: todo editable excepto el nombre (identificador del programa)
            bloquearCampos(false, true);
            btnGuardar.style.display = '';
            btnGuardar.textContent = 'Actualizar';
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

        const payload = {
            // En edición el nombre está deshabilitado: se toma del programa seleccionado.
            nombre: editando ? seleccionado.nombre : inNombre.value.trim(),
            nivel: selNivel.value,
            rama: selRama.value,
            semestre: selSemestre.value,
        };
        if (!payload.nombre || !payload.nivel || !payload.rama || !payload.semestre) {
            mostrarMensaje('Completa Nombre, Nivel, Rama y Semestre.', 'error');
            return;
        }

        btnGuardar.disabled = true;
        mostrarMensaje(editando ? 'Actualizando programa...' : 'Registrando programa...', 'info');
        try {
            const resp = await fetch(editando ? '/catalogo_programas/modificar' : '/catalogo_programas/alta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await resp.json().catch(() => ({}));
            if (resp.ok && data.status === 'ok') {
                if (editando) modoRegistro(); else form.reset();
                mostrarMensaje(data.mensaje || (editando ? 'Programa modificado correctamente.' : 'Programa registrado correctamente.'), 'ok');
                await cargarProgramas();
            } else {
                mostrarMensaje(data.mensaje || data.detail || (editando ? 'No se pudo modificar el programa.' : 'No se pudo registrar el programa.'), 'error');
            }
        } catch (err) {
            mostrarMensaje('Error de conexión: ' + err.message, 'error');
        } finally {
            btnGuardar.disabled = false;
        }
    });

    // ---------- Baja ----------
    btnEliminar.addEventListener('click', function () {
        if (!seleccionado) return;
        modalNombre.textContent = seleccionado.nombre;
        modal.classList.add('show');
    });

    modalCancelar.addEventListener('click', e => { e.preventDefault(); modal.classList.remove('show'); });
    modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });

    modalConfirmar.addEventListener('click', async function () {
        modal.classList.remove('show');
        if (!seleccionado) return;
        const nombre = seleccionado.nombre;
        mostrarMensaje('Dando de baja el programa...', 'info');
        try {
            const resp = await fetch('/catalogo_programas/baja', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nombre }),
            });
            const data = await resp.json().catch(() => ({}));
            if (resp.ok && data.status === 'ok') {
                modoRegistro();
                mostrarMensaje(data.mensaje || 'Programa dado de baja correctamente.', 'ok');
                await cargarProgramas();
            } else {
                mostrarMensaje(data.mensaje || data.detail || 'No se pudo dar de baja el programa.', 'error');
            }
        } catch (err) {
            mostrarMensaje('Error de conexión: ' + err.message, 'error');
        }
    });

    // ---------- Filtros ----------
    filtroTexto.addEventListener('input', pintarTabla);
    filtroEstatus.addEventListener('change', pintarTabla);
    btnLimpiarFiltros.addEventListener('click', function () {
        filtroTexto.value = '';
        filtroEstatus.value = '';
        pintarTabla();
    });
});
