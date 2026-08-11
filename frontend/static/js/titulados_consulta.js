/********************************************************************************
 * PARTE 1: CONSULTA Y CONTROL DE CAPTURA (Originalmente titulados_consulta.js)
 ********************************************************************************/

function seleccionarTodasEdades(seleccionar) {
    const checkboxes = document.querySelectorAll('.checkbox-edad');
    checkboxes.forEach(cb => cb.checked = seleccionar);
    actualizarContadorEdades();
}

function actualizarContadorEdades() {
    const checkboxes = document.querySelectorAll('.checkbox-edad:checked');
    const count = checkboxes.length;
    const countElement = document.getElementById('edades-seleccionadas-count');
    if (countElement) {
        countElement.textContent = `${count} edad${count !== 1 ? 'es' : ''} seleccionada${count !== 1 ? 's' : ''}`;
        countElement.style.color = count > 0 ? '#28a745' : '#636569';
        countElement.style.fontWeight = count > 0 ? '600' : 'normal';
    }
}


function agregarFilasTitulados() {
    const programa = document.getElementById('programa');
    const modalidad = document.getElementById('modalidad');
    const boleta = document.getElementById('filtro-boleta');
    const tipoTitulacion = document.getElementById('filtro-generacion');
    const nombreRama = datosFilas[0]?.Nombre_Rama || 'Rama Desconocida';

    const checkboxesSeleccionados = document.querySelectorAll('.checkbox-edad:checked');

    const mostrarAlerta = (msg) => {
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'warning',
                title: 'Campos incompletos',
                text: msg,
                confirmButtonColor: '#750946',
                confirmButtonText: 'Entendido'
            });
        } else {
            alert(msg);
        }
    };

    if (!programa || !programa.value || programa.value === "" || programa.value === "0") {
        mostrarAlerta('Por favor seleccione un programa.');
        return;
    }
    if (!modalidad || !modalidad.value || modalidad.value === "" || modalidad.value === "0") {
        mostrarAlerta('Por favor seleccione una modalidad.');
        return;
    }
    if (!boleta || !boleta.value || boleta.value === "" || boleta.value === "0") {
        mostrarAlerta('Por favor seleccione una boleta.');
        return;
    }
    if (!tipoTitulacion || !tipoTitulacion.value || tipoTitulacion.value === "" || tipoTitulacion.value === "0") {
        mostrarAlerta('Por favor seleccione un tipo de titulación.');
        return;
    }
    if (checkboxesSeleccionados.length === 0) {
        mostrarAlerta('Por favor seleccione al menos un grupo de edad.');
        return;
    }

    let filasAgregadas = 0;
    let filasDuplicadas = 0;

    checkboxesSeleccionados.forEach(checkbox => {
        const edadValor = checkbox.value;
        const edadNombre = checkbox.dataset.nombre;

        // 1. Evitar duplicados en las filas que ya están renderizadas en la pantalla de captura
        const existeEnPantalla = filasTitulados.some(fila =>
            fila.programa === programa.value &&
            fila.modalidad === modalidad.value &&
            fila.boleta === boleta.value &&
            fila.tipoTitulacion === tipoTitulacion.value &&
            fila.edad === edadValor
        );

        if (existeEnPantalla) {
            filasDuplicadas++;
            console.warn(`⚠️ Ya existe una fila en la tabla para edad: ${edadNombre}`);
            return;
        }

        // 2. BUSCAR DATOS PREVIOS EN LA VARIABLE GLOBAL (datosFilas)
        const progNom = programa.options[programa.selectedIndex].text.trim();
        const modNom = modalidad.options[modalidad.selectedIndex].text.trim();
        const bolNom = boleta.options[boleta.selectedIndex].text.trim();
        const tipoNom = tipoTitulacion.options[tipoTitulacion.selectedIndex].text.trim();
        const edNom = edadNombre.trim();

        const turnosObj = {};

        turnosDisponibles.forEach(t => {
            const turno = (t.nombre || t).trim();
            // Buscamos si existe registro guardado para este turno en versión HOMBRE
            const registroHombre = (datosFilas || []).find(d =>
                d &&
                (d.Nombre_Programa || '').trim() === progNom &&
                (d.Modalidad || '').trim() === modNom &&
                String(d.Boleta || '').trim() === bolNom &&
                (d.Tipo_Titulacion || '').trim() === tipoNom &&
                String(d.Grupo_Edad || d.Edad || '').trim() === edNom &&
                (d.Turno || '').trim() === turno &&
                (d.Sexo === 'Hombre' || d.Sexo === 'H' || d.Sexo === 'HOMBRE')
            );

            // Buscamos si existe registro guardado para este turno en versión MUJER
            const registroMujer = (datosFilas || []).find(d =>
                d &&
                (d.Nombre_Programa || '').trim() === progNom &&
                (d.Modalidad || '').trim() === modNom &&
                String(d.Boleta || '').trim() === bolNom &&
                (d.Tipo_Titulacion || '').trim() === tipoNom &&
                String(d.Grupo_Edad || d.Edad || '').trim() === edNom &&
                (d.Turno || '').trim() === turno &&
                (d.Sexo === 'Mujer' || d.Sexo === 'M' || d.Sexo === 'MUJER')
            );

            const cantH = registroHombre ? (registroHombre.Titulados !== undefined ? registroHombre.Titulados : registroHombre.Egresados) : '';
            const cantM = registroMujer ? (registroMujer.Titulados !== undefined ? registroMujer.Titulados : registroMujer.Egresados) : '';

            // Asignamos el valor encontrado en la BD, o un string vacío si no hay antecedentes
            turnosObj[turno] = {
                hombres: (cantH !== null && cantH !== undefined && cantH !== '') ? cantH : '',
                mujeres: (cantM !== null && cantM !== undefined && cantM !== '') ? cantM : ''
            };
        });

        // 3. Crear la estructura de la fila con los datos (vacíos o recuperados)
        const fila = {
            id: Date.now() + Math.random(),
            programa: programa.value,
            programaNombre: programa.options[programa.selectedIndex].text,
            modalidad: modalidad.value,
            modalidadNombre: modalidad.options[modalidad.selectedIndex].text,
            boleta: boleta.value,
            boletaNombre: boleta.options[boleta.selectedIndex].text,
            tipoTitulacion: tipoTitulacion.value,
            tipoTitulacionNombre: tipoTitulacion.options[tipoTitulacion.selectedIndex].text,
            edad: edadValor,
            edadNombre: edadNombre,
            ramaNombre: nombreRama,
            turnos: turnosObj
        };

        filasTitulados.push(fila);
        filasAgregadas++;
    });

    if (filasDuplicadas > 0) console.warn(`⚠️ ${filasDuplicadas} fila(s) duplicada(s) omitidas`);

    if (filasAgregadas > 0) {
        generarCabeceraTabla();
        renderizarTablaTituladosCaptura();
        console.log(`✅ ${filasAgregadas} fila(s) procesada(s)`);

        if (typeof Swal !== 'undefined') {
            const Toast = Swal.mixin({
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 1800,
                didOpen: (toast) => {
                    toast.addEventListener('mouseenter', Swal.stopTimer);
                    toast.addEventListener('mouseleave', Swal.resumeTimer);
                }
            });
            Toast.fire({
                icon: 'success',
                title: filasAgregadas === 1 ? 'Fila agregada correctamente' : `${filasAgregadas} filas agregadas correctamente`
            });
        }
    } else if (filasDuplicadas > 0) {
        if (typeof Swal !== 'undefined') {
            const Toast = Swal.mixin({
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 1800
            });
            Toast.fire({
                icon: 'info',
                title: 'Las filas ya se encuentran en la tabla'
            });
        }
    }
}

function generarCabeceraTabla() {
    const thead = document.getElementById('titulados-thead');
    if (!thead) return;

    // Fila 1: Boleta, Generación, Edad, por cada turno su nombre (colspan 2), Acciones
    let fila1 = '<tr style="background: linear-gradient(135deg, #750946 0%, #8b2635 100%); color: white;">';
    fila1 += '<th rowspan="2" style="padding:12px 15px; text-align:center; font-weight:600; font-size:14px; border:1px solid rgba(255,255,255,0.2); vertical-align:middle;">Boleta</th>';
    fila1 += '<th rowspan="2" style="padding:12px 15px; text-align:center; font-weight:600; font-size:14px; border:1px solid rgba(255,255,255,0.2); vertical-align:middle;">Tipo de Titulación</th>';
    fila1 += '<th rowspan="2" style="padding:12px 15px; text-align:center; font-weight:600; font-size:14px; border:1px solid rgba(255,255,255,0.2); vertical-align:middle;">Edad</th>';

    const turnos = [...new Set(datosFilas.map(f => f.Turno))];

    turnos.forEach(turno => {
        fila1 += `<th colspan="2" style="padding:10px 15px; text-align:center; font-weight:700; font-size:13px; border:1px solid rgba(255,255,255,0.2); background:rgba(0,0,0,0.15);">${turno}</th>`;
    });

    fila1 += '</tr>';

    // Fila 2: H y M por cada turno
    let fila2 = '<tr style="background: rgba(110,3,67,0.85); color: white;">';
    turnos.forEach(() => {
        fila2 += '<th style="padding:8px 10px; text-align:center; font-size:12px; border:1px solid rgba(255,255,255,0.2); color:#b3e5fc;">H</th>';
        fila2 += '<th style="padding:8px 10px; text-align:center; font-size:12px; border:1px solid rgba(255,255,255,0.2); color:#f8bbd0;">M</th>';
    });
    fila2 += '</tr>';

    thead.innerHTML = fila1 + fila2;
}

function renderizarTablaTituladosCaptura() {
    const tbody = document.getElementById('titulados-tbody');
    if (!tbody) return;

    const colspan = 3 + turnosDisponibles.length * 2;

    if (filasTitulados.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="${colspan}" style="text-align:center; padding:40px; color:#636569;">
                    <div style="font-size:48px; margin-bottom:15px;">📚</div>
                    <p style="font-size:16px; margin:0;">No hay registros. Use los filtros arriba para agregar filas.</p>
                </td>
            </tr>`;
        ajustarScrollTablaTitulados();
        return;
    }

    tbody.innerHTML = '';

    filasTitulados.forEach((fila, index) => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #dee2e6';
        if (index % 2 === 0) tr.style.background = '#fafafa';

        let celdas = `
            <td style="padding:12px; text-align:center;">${fila.boletaNombre}</td>
            <td style="padding:12px; text-align:center;">${fila.tipoTitulacionNombre}</td>
            <td style="padding:12px; text-align:center; font-weight:600;">${fila.edadNombre}</td>`;

        turnosDisponibles.forEach(turno => {
            const vals = fila.turnos[turno] || { hombres: '', mujeres: '' };
            celdas += `
            <td style="padding:8px; text-align:center;">
                <div style="display:inline-flex;align-items:center;gap:3px;padding:2px 4px;background:#e3f2fd;border-radius:4px;border:1px solid #90caf9;line-height:1;">
                    <div style="font-weight:700;color:#1976d2;font-size:11px;min-width:14px;text-align:center;">H</div>
                    <input type="number" min="0" max="9999" maxlength="4"
                        value="${vals.hombres}"
                        onkeydown="if(['-','.','+','e','E',','].includes(event.key)) event.preventDefault();"
                        oninput="this.value=this.value.replace(/[^0-9]/g,'').slice(0,4); actualizarValorTitulado(${fila.id}, '${turno}', 'hombres', this.value)"
                        style="width:42px;padding:2px 3px;border:2px solid #2196f3;border-radius:3px;background:#fff;color:#1976d2;font-weight:600;text-align:center;font-size:11px;">
                </div>
            </td>
            <td style="padding:8px; text-align:center;">
                <div style="display:inline-flex;align-items:center;gap:3px;padding:2px 4px;background:#fce4ec;border-radius:4px;border:1px solid #f48fb1;line-height:1;">
                    <div style="font-weight:700;color:#c2185b;font-size:11px;min-width:14px;text-align:center;">M</div>
                    <input type="number" min="0" max="9999" maxlength="4"
                        value="${vals.mujeres}"
                        onkeydown="if(['-','.','+','e','E',','].includes(event.key)) event.preventDefault();"
                        oninput="this.value=this.value.replace(/[^0-9]/g,'').slice(0,4); actualizarValorTitulado(${fila.id}, '${turno}', 'mujeres', this.value)"
                        style="width:42px;padding:2px 3px;border:2px solid #e91e63;border-radius:3px;background:#fff;color:#c2185b;font-weight:600;text-align:center;font-size:11px;">
                </div>
            </td>`;
        });

        tr.innerHTML = celdas;
        tbody.appendChild(tr);
    });

    ajustarScrollTablaTitulados();
}

function ajustarScrollTablaTitulados() {
    const tbody = document.getElementById('titulados-tbody');
    if (!tbody) return;

    if (filasTitulados.length > 5) {
        const primeraFila = tbody.querySelector('tr');
        const altoFila = primeraFila ? primeraFila.getBoundingClientRect().height : 58;
        tbody.style.maxHeight = `${Math.ceil(altoFila * 5)}px`;
        tbody.style.overflowY = 'auto';
    } else {
        tbody.style.maxHeight = 'none';
        tbody.style.overflowY = 'visible';
    }
}

function actualizarValorTitulado(filaId, turno, sexo, valor) {
    const fila = filasTitulados.find(f => f.id === filaId);
    if (!fila) return;

    if (!fila.turnos[turno]) {
        fila.turnos[turno] = { hombres: '', mujeres: '' };
    }

    fila.turnos[turno][sexo] = parseInt(valor) || 0;
}

async function eliminarFilaTitulado(id) {
    if (typeof Swal !== 'undefined') {
        const confirmacion = await Swal.fire({
            title: '¿Está seguro de eliminar este registro?',
            text: "Esta acción no se puede deshacer.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc3545',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        });
        if (confirmacion.isConfirmed) {
            filasTitulados = filasTitulados.filter(f => f.id !== id);
            renderizarTablaTituladosCaptura();
            Swal.fire({
                icon: 'success',
                title: 'Registro eliminado',
                timer: 1500,
                showConfirmButton: false
            });
        }
    } else {
        if (confirm('¿Está seguro de eliminar este registro?')) {
            filasTitulados = filasTitulados.filter(f => f.id !== id);
            renderizarTablaTituladosCaptura();
        }
    }
}

async function limpiarTabla() {
    if (filasTitulados.length === 0) return;

    if (typeof Swal !== 'undefined') {
        const confirmacion = await Swal.fire({
            title: '¿Está seguro de limpiar la tabla?',
            text: `Se eliminarán los ${filasTitulados.length} registros agregados en la captura.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc3545',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Sí, limpiar',
            cancelButtonText: 'Cancelar'
        });
        if (confirmacion.isConfirmed) {
            filasTitulados = [];
            renderizarTablaTituladosCaptura();
            console.log('Tabla limpiada completamente');
            Swal.fire({
                icon: 'success',
                title: 'Tabla limpiada',
                timer: 1500,
                showConfirmButton: false
            });
        }
    } else {
        if (confirm(`¿Está seguro de eliminar los ${filasTitulados.length} registros?`)) {
            filasTitulados = [];
            renderizarTablaTituladosCaptura();
            console.log('Tabla limpiada completamente');
        }
    }
}

async function limpiarFormulario() {
    if (typeof Swal !== 'undefined') {
        const confirmacion = await Swal.fire({
            title: '¿Está seguro de limpiar todo?',
            text: "Se borrarán todos los registros y se reiniciará el formulario.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc3545',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Sí, limpiar todo',
            cancelButtonText: 'Cancelar'
        });
        if (confirmacion.isConfirmed) {
            filasTitulados = [];
            renderizarTablaTituladosCaptura();

            // Limpiar selección de checkboxes de edad
            const checkboxes = document.querySelectorAll('.checkbox-edad');
            checkboxes.forEach(cb => cb.checked = false);
            actualizarContadorEdades();

            Swal.fire({
                icon: 'success',
                title: 'Formulario limpiado',
                timer: 1500,
                showConfirmButton: false
            });
        }
    } else {
        if (confirm('¿Está seguro de limpiar todos los datos? Esta acción no se puede deshacer.')) {
            filasTitulados = [];
            renderizarTablaTituladosCaptura();
            const checkboxes = document.querySelectorAll('.checkbox-edad');
            checkboxes.forEach(cb => cb.checked = false);
            actualizarContadorEdades();
        }
    }
}


document.addEventListener('DOMContentLoaded', function () {

    const btnConsultar = document.getElementById('btn-ver-resumen-director');

    const selectPeriodo = document.getElementById('select-periodo-director');
    const selectNivel = document.getElementById('select-nivel-director');

    const selectPeriodoSuperior = document.getElementById('select-periodo-superior');
    const selectNivelSuperior = document.getElementById('select-nivel-superior');
    const selectUnidadAcademicaSuperior = document.getElementById('select-ua-superior');

    // Habilitar botón solo cuando ambos selects tienen valor
    function verificarFiltros() {

        const listo = selectPeriodo && selectNivel
            ? selectPeriodo.value !== '' && selectNivel.value !== ''
            : false; // Se hace false en caso de que alguno de los selects no exista en el DOM

        const listoSuperior = selectPeriodoSuperior && selectNivelSuperior && selectUnidadAcademicaSuperior
            ? selectPeriodoSuperior.value !== '' && selectNivelSuperior.value !== '' && selectUnidadAcademicaSuperior.value !== ''
            : false;

        btnConsultar.disabled = !(listo || listoSuperior);
    }

    // Filtramos los que no existen antes de agregar el listener
    [selectPeriodo, selectNivel, selectPeriodoSuperior, selectNivelSuperior, selectUnidadAcademicaSuperior]
        .filter(select => select !== null) // Se filtran los que estan distintos de null
        .forEach(select => select.addEventListener('change', verificarFiltros));

    // Al hacer clic, navegar al acuse de titulados
    if (btnConsultar) {
        btnConsultar.addEventListener('click', function () {
            let periodo, nivel, unidad;

            if (selectPeriodo && selectNivel) {
                // Flujo director
                periodo = selectPeriodo.value;
                nivel = selectNivel.value;
                unidad = document.getElementById('datos-sesion').dataset.unidad; // viene del contexto Jinja2
            } else if (selectPeriodoSuperior && selectNivelSuperior && selectUnidadAcademicaSuperior) {
                // Flujo superior
                periodo = selectPeriodoSuperior.value;
                nivel = selectNivelSuperior.value;
                unidad = selectUnidadAcademicaSuperior.value;
            }

            if (!periodo || !nivel || !unidad) return;

            const url = `/titulados/acuse-validacion`
                + `?periodo=${encodeURIComponent(periodo)}`
                + `&nivel=${encodeURIComponent(nivel)}`
                + `&unidad=${encodeURIComponent(unidad)}`;

            window.location.href = url;
        });
    }

});


/********************************************************************************
 * PARTE 2: PERSISTENCIA, INFORMES Y FILTROS DE TABLAS (Originalmente titulados_datos.js)
 ********************************************************************************/

function actualizarValorFila(idFila, campo, valor) {

    const numero = valor === "" ? 0 : Math.max(0, Number(valor));

    const fila = filasTitulados.find(f => f.id === idFila);

    if (fila) {
        fila[campo] = numero;
    }

    console.log("Filas actualizadas:", filasTitulados);
}

function actualizarDatosFilasDesdeCaptura() {
    if (!datosFilas) {
        datosFilas = [];
    }
    if (!filasTitulados || filasTitulados.length === 0) return;

    filasTitulados.forEach(fila => {
        const programaNombre = fila.programaNombre || "";
        const modalidadNombre = fila.modalidadNombre || "";
        const boletaNombre = fila.boletaNombre || "";
        const tipoTitulacionNombre = fila.tipoTitulacionNombre || "";
        const edadNombre = fila.edadNombre || "";

        if (!fila.turnos) return;

        Object.keys(fila.turnos).forEach(turno => {
            const turnData = fila.turnos[turno];
            if (!turnData) return;

            // 1. Hombres
            let registroHombre = datosFilas.find(d => 
                d &&
                d.Nombre_Programa === programaNombre &&
                d.Modalidad === modalidadNombre &&
                String(d.Boleta) === String(boletaNombre) &&
                d.Tipo_Titulacion === tipoTitulacionNombre &&
                d.Grupo_Edad === edadNombre &&
                d.Turno === turno &&
                (d.Sexo === 'Hombre' || d.Sexo === 'H' || d.Sexo === 'HOMBRE')
            );
            const valHombres = parseInt(turnData.hombres) || 0;
            if (registroHombre) {
                registroHombre.Titulados = valHombres;
                registroHombre.Id_Semaforo = 2; // En Proceso
            } else {
                datosFilas.push({
                    Nombre_Programa: programaNombre,
                    Nombre_Rama: fila.ramaNombre || "",
                    Nivel: "Licenciatura",
                    Modalidad: modalidadNombre,
                    Turno: turno,
                    Boleta: boletaNombre,
                    Tipo_Titulacion: tipoTitulacionNombre,
                    Grupo_Edad: edadNombre,
                    Sexo: 'Hombre',
                    Titulados: valHombres,
                    Id_Semaforo: 2
                });
            }

            // 2. Mujeres
            let registroMujer = datosFilas.find(d => 
                d &&
                d.Nombre_Programa === programaNombre &&
                d.Modalidad === modalidadNombre &&
                String(d.Boleta) === String(boletaNombre) &&
                d.Tipo_Titulacion === tipoTitulacionNombre &&
                d.Grupo_Edad === edadNombre &&
                d.Turno === turno &&
                (d.Sexo === 'Mujer' || d.Sexo === 'M' || d.Sexo === 'MUJER')
            );
            const valMujeres = parseInt(turnData.mujeres) || 0;
            if (registroMujer) {
                registroMujer.Titulados = valMujeres;
                registroMujer.Id_Semaforo = 2; // En Proceso
            } else {
                datosFilas.push({
                    Nombre_Programa: programaNombre,
                    Nombre_Rama: fila.ramaNombre || "",
                    Nivel: "Licenciatura",
                    Modalidad: modalidadNombre,
                    Turno: turno,
                    Boleta: boletaNombre,
                    Tipo_Titulacion: tipoTitulacionNombre,
                    Grupo_Edad: edadNombre,
                    Sexo: 'Mujer',
                    Titulados: valMujeres,
                    Id_Semaforo: 2
                });
            }
        });
    });
}

function guardarAvance(esBorrado = false) {
    if (!esBorrado) {
        if (!filasTitulados || filasTitulados.length === 0) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Sin datos para guardar',
                    text: 'No hay datos para guardar. Por favor agregue al menos un registro en la tabla de captura.',
                    confirmButtonColor: '#750946',
                    confirmButtonText: 'Entendido'
                });
            } else {
                alert('No hay datos para guardar. Por favor agregue al menos un registro en la tabla de captura.');
            }
            return;
        }

        const tieneDatos = filasTitulados.some(fila =>
            Object.values(fila.turnos || {}).some(t => {
                const h = parseInt(t.hombres) || 0;
                const m = parseInt(t.mujeres) || 0;
                return h > 0 || m > 0;
            })
        );

        if (!tieneDatos) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Sin datos para guardar',
                    text: 'No hay datos para guardar. Por favor ingrese cantidades mayores a cero en la tabla de captura.',
                    confirmButtonColor: '#750946',
                    confirmButtonText: 'Entendido'
                });
            } else {
                alert('No hay datos para guardar. Por favor ingrese cantidades mayores a cero en la tabla de captura.');
            }
            return;
        }
    }

    const loadingTitle = esBorrado ? 'Eliminando registro...' : 'Guardando avance...';
    const successTitle = esBorrado ? '¡Registro eliminado!' : '¡Guardado exitoso!';
    const successText = esBorrado 
        ? 'El registro ha sido eliminado correctamente y la tabla de informe ha sido actualizada.' 
        : 'El avance se ha guardado y la tabla de informe ha sido actualizada.';
    const errorTitle = esBorrado ? 'Error al eliminar' : 'Error al guardar';
    const errorText = esBorrado 
        ? 'Error al eliminar el registro, por favor intente de nuevo.' 
        : 'Error al guardar el avance, por favor intente de nuevo.';

    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: loadingTitle,
            text: 'Por favor espere',
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
    }

    fetch('/titulados/guardar-avance-titulados', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(filasTitulados)
    })
    .then(async response => {
        if (response.status === 401) {
            throw new Error('SESSION_EXPIRED');
        }
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || errData.detail || 'Error en la respuesta del servidor');
        }
        return response.json();
    })
    .then(data => {
        console.log('Respuesta del servidor:', data);
        
        try {
            // Actualizar datos locales y re-renderizar tabla de informe
            actualizarDatosFilasDesdeCaptura();
            renderizarTablaTitulados(datosFilas);
            filtrarPorSelects();
            actualizarSemaforoTitulados();
        } catch (e) {
            console.error("Error al actualizar la tabla de informes localmente:", e);
        }

        try {
            // Limpiar formulario de captura
            filasTitulados = [];
            renderizarTablaTituladosCaptura();
            const checkboxes = document.querySelectorAll('.checkbox-edad');
            checkboxes.forEach(cb => cb.checked = false);
            actualizarContadorEdades();
        } catch (e) {
            console.error("Error al limpiar el formulario de captura:", e);
        }

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'success',
                title: successTitle,
                text: successText,
                timer: 2500,
                showConfirmButton: false
            });
        } else {
            alert(successText);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        if (error.message === 'SESSION_EXPIRED') {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Sesión expirada',
                    text: 'Su sesión ha expirado debido al reinicio del servidor. Por favor inicie sesión nuevamente.',
                    confirmButtonColor: '#750946',
                    confirmButtonText: 'Iniciar Sesión'
                }).then(() => {
                    window.location.href = '/login/';
                });
            } else {
                alert('Su sesión ha expirado. Por favor inicie sesión nuevamente.');
                window.location.href = '/login/';
            }
            return;
        }
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'error',
                title: errorTitle,
                text: errorText,
                confirmButtonColor: '#750946',
                confirmButtonText: 'Entendido'
            });
        } else {
            alert(errorText);
        }
    });
}

//Finalizar Captura

async function finalizarCapturaTitulados() {
    const programa = document.getElementById('programa').value;
    const modalidad = document.getElementById('modalidad').value;

    if (!programa || programa === "" || programa === "0") {
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'warning',
                title: 'Campos incompletos',
                text: 'Por favor selecciona un programa.',
                confirmButtonColor: '#750946',
                confirmButtonText: 'Entendido'
            });
        } else {
            alert("Por favor selecciona un programa.");
        }
        return;
    }

    if (!modalidad || modalidad === "" || modalidad === "0") {
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'warning',
                title: 'Campos incompletos',
                text: 'Por favor selecciona una modalidad.',
                confirmButtonColor: '#750946',
                confirmButtonText: 'Entendido'
            });
        } else {
            alert("Por favor selecciona una modalidad.");
        }
        return;
    }

    if (typeof Swal !== 'undefined') {
        const confirmacion = await Swal.fire({
            title: '⚠️ ¿Desea finalizar la captura?',
            text: 'Una vez finalizada, el estado de la captura cambiará a finalizado y no se podrán realizar más cambios.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#28a745',
            cancelButtonColor: '#dc3545',
            confirmButtonText: 'Sí, finalizar',
            cancelButtonText: 'Cancelar'
        });
        if (!confirmacion.isConfirmed) {
            return;
        }

        Swal.fire({
            title: 'Finalizando captura...',
            text: 'Por favor espere',
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
    } else {
        if (!confirm('¿Está seguro de finalizar la captura para este programa y modalidad?')) {
            return;
        }
    }

    fetch('/titulados/finalizar-titulados', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            datos: filasTitulados.length > 0 ? filasTitulados : datosFilasFiltrados,
            programa: programa,
            modalidad: modalidad,
            origen: filasTitulados.length > 0 ? "captura" : "db"
        })
    })
        .then(async response => {
            if (response.status === 401) {
                throw new Error('SESSION_EXPIRED');
            }
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || errData.detail || 'Error en la respuesta del servidor');
            }
            return response.json();
        })
        .then(data => {
            console.log('Respuesta del servidor:', data);
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'success',
                    title: '¡Captura Finalizada!',
                    text: 'Se ha finalizado el programa y modalidad correctamente.',
                    timer: 2000,
                    showConfirmButton: false
                }).then(() => {
                    window.location.reload();
                });
            } else {
                alert('Finalizado programa modalidad correctamente');
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            if (error.message === 'SESSION_EXPIRED') {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Sesión expirada',
                        text: 'Su sesión ha expirado debido al reinicio del servidor. Por favor inicie sesión nuevamente.',
                        confirmButtonColor: '#750946',
                        confirmButtonText: 'Iniciar Sesión'
                    }).then(() => {
                        window.location.href = '/login/';
                    });
                } else {
                    alert('Su sesión ha expirado. Por favor inicie sesión nuevamente.');
                    window.location.href = '/login/';
                }
                return;
            }
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Error al finalizar',
                    text: error.message || 'Error al finalizar programa modalidad, por favor intente de nuevo.',
                    confirmButtonColor: '#750946',
                    confirmButtonText: 'Entendido'
                });
            } else {
                alert(error.message || 'Error al finalizar programa modalidad, por favor intente de nuevo.');
            }
        });
}

function agruparPorSexo(datosFilas) {
    const grupos = {};

    datosFilas.forEach(fila => {
        // Clave única para agrupar filas "iguales" excepto por el sexo
        const clave = [
            fila.Nombre_Programa,
            fila.Modalidad,
            fila.Turno,
            fila.Boleta,
            fila.Tipo_Titulacion,
            fila.Grupo_Edad
        ].join('|');

        if (!grupos[clave]) {
            grupos[clave] = {
                Nombre_Programa: fila.Nombre_Programa,
                Nombre_Rama: fila.Nombre_Rama || "",
                Modalidad: fila.Modalidad,
                Turno: fila.Turno,
                Boleta: fila.Boleta,
                Tipo_Titulacion: fila.Tipo_Titulacion,
                Grupo_Edad: fila.Grupo_Edad,
                Hombres: 0,
                Mujeres: 0,
            };
        }

        const sexo = (fila.Sexo || '').trim().toUpperCase();
        const cantidad = Number(fila.Titulados) || 0;

        if (sexo === 'H' || sexo === 'HOMBRE' || sexo === 'M') {
            grupos[clave].Hombres += cantidad;
        } else if (sexo === 'F' || sexo === 'MUJER' || sexo === 'W') {
            grupos[clave].Mujeres += cantidad;
        }
    });

    return Object.values(grupos).filter(g => g.Hombres > 0 || g.Mujeres > 0);
}

function renderizarTablaTitulados(datosFilas) {
    const tbody = document.querySelector('#informe-titulados-table tbody');
    if (!tbody) return; // Se previene error si no se encuentra en el DOM
    if (!datosFilas || datosFilas.length === 0) return;

    // Agrupar antes de renderizar
    const filas = agruparPorSexo(datosFilas);

    tbody.innerHTML = '';

    if (filas.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="10" style="text-align: center; padding: 30px; color: #999;">
                    <div style="font-size: 48px; margin-bottom: 10px;">📋</div>
                    <div>No hay datos guardados aún. Guarde registros para ver el informe.</div>
                </td>
            </tr>`;
        return;
    }

    let html = '';
    let totalGeneralH = 0, totalGeneralM = 0;

    filas.forEach((fila, i) => {
        const total = fila.Hombres + fila.Mujeres;
        const totalH = fila.Hombres;
        const totalM = fila.Mujeres;
        totalGeneralH += totalH;
        totalGeneralM += totalM;

        // Codificar los parámetros de texto para evitar errores de comillas en HTML
        const progEnc = encodeURIComponent(fila.Nombre_Programa);
        const modEnc = encodeURIComponent(fila.Modalidad);
        const bolEnc = encodeURIComponent(fila.Boleta);
        const tipoEnc = encodeURIComponent(fila.Tipo_Titulacion);
        const edadEnc = encodeURIComponent(fila.Grupo_Edad);
        const ramEnc = encodeURIComponent(fila.Nombre_Rama || "");

        // Verificar si este programa y modalidad en particular ya están finalizados (Id_Semaforo === 3)
        const esFinalizado = datosFilas.some(d => 
            d &&
            d.Nombre_Programa === fila.Nombre_Programa &&
            d.Modalidad === fila.Modalidad &&
            d.Id_Semaforo === 3
        );

        html += `<tr style="background: ${i % 2 === 0 ? '#f9f9f9' : 'white'}">
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">
                ${esFinalizado ? '<input type="checkbox" disabled style="transform: scale(1.1); opacity: 0.5; cursor: not-allowed;" />' : `
                <input type="checkbox" class="seleccionar-fila-informe" 
                       data-programa="${progEnc}" 
                       data-modalidad="${modEnc}" 
                       data-boleta="${bolEnc}" 
                       data-tipo-titulacion="${tipoEnc}" 
                       data-edad="${edadEnc}" 
                       data-rama="${ramEnc}"
                       data-turno="${encodeURIComponent(fila.Turno || '')}"
                       style="transform: scale(1.1); cursor: pointer;" />
                `}
            </td>
            <td style="padding:10px; border:1px solid #ddd;">${fila.Nombre_Programa}</td>
            <td style="padding:10px; border:1px solid #ddd;">${fila.Modalidad}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Turno}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Boleta}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Tipo_Titulacion}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Grupo_Edad}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${Number(fila.Hombres || 0).toLocaleString('en-US')}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${Number(fila.Mujeres || 0).toLocaleString('en-US')}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd; font-weight:700;">${Number(total || 0).toLocaleString('en-US')}</td>
        </tr>`;
    });

    html += `<tr id="informe-total-row-titulados" style="background: linear-gradient(135deg, #750946 0%, #a3195b 100%); color:white; font-weight:700;">
        <td colspan="7" style="padding:12px; border:1px solid #ddd; text-align:right;">TOTAL GENERAL:</td>
        <td class="total-h" style="padding:12px; text-align:center; border:1px solid #ddd;">${Number(totalGeneralH || 0).toLocaleString('en-US')}</td>
        <td class="total-m" style="padding:12px; text-align:center; border:1px solid #ddd;">${Number(totalGeneralM || 0).toLocaleString('en-US')}</td>
        <td class="total-g" style="padding:12px; text-align:center; font-size:18px;">${Number(totalGeneralH + totalGeneralM || 0).toLocaleString('en-US')}</td>
    </tr>`;

    tbody.innerHTML = html;
}


// Filtros de resumen

function initTableFilters() {

    const headers = document.querySelectorAll('.filterable-header');
    updateFilterHeaderStates();

    headers.forEach(header => {
        header.addEventListener('click', function (e) {
            e.stopPropagation();
            const columnIndex = parseInt(this.dataset.column);

            if (currentFilterDropdown) {
                currentFilterDropdown.remove();
                if (currentFilterDropdown.dataset.column == columnIndex) {
                    currentFilterDropdown = null;
                    currentFilterHeaderEl = null;
                    unbindFilterDropdownAutoPosition();
                    clearHeaderOpenState();
                    return;
                }
            }

            showFilterDropdown(this, columnIndex);
        });
    });
}

function clearHeaderOpenState() {
    document.querySelectorAll('.filterable-header.is-open').forEach(header => {
        header.classList.remove('is-open');
    });
}

function updateFilterHeaderStates() {
    const headers = document.querySelectorAll('.filterable-header');
    headers.forEach(header => {
        const columnKey = String(header.dataset.column);
        const hasFilter = Object.prototype.hasOwnProperty.call(activeFilters, columnKey);
        header.classList.toggle('has-filter', hasFilter);
    });
}

function showFilterDropdown(headerElement, columnIndex) {
    const table = document.getElementById('informe-titulados-table');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'))
        .filter(row => row.id !== 'informe-total-row-titulados' && !row.querySelector('td[colspan]'))
        .filter(row => row.style.display !== 'none');

    if (rows.length === 0) {
        console.log('⚠️ No hay datos para filtrar');
        return;
    }

    // Recopilar valores únicos de la columna
    const uniqueValues = new Set();
    rows.forEach(row => {
        const cell = row.cells[columnIndex];
        if (cell) {
            const value = cell.textContent.trim();
            uniqueValues.add(value);
        }
    });

    const sortedValues = Array.from(uniqueValues).sort((a, b) => {
        // Ordenar numéricamente si ambos son números
        const numA = parseFloat(a);
        const numB = parseFloat(b);
        if (!isNaN(numA) && !isNaN(numB)) {
            return numA - numB;
        }
        return a.localeCompare(b, 'es', { numeric: true });
    });

    const dropdownWidth = calculateDynamicDropdownWidth(sortedValues, headerElement);

    // Crear dropdown
    const dropdown = document.createElement('div');
    dropdown.className = 'filter-dropdown active';
    dropdown.dataset.column = columnIndex;

    // Prevenir que clicks dentro del dropdown lo cierren
    dropdown.addEventListener('click', function (e) {
        e.stopPropagation();
    });

    // Contenedor de opciones
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'filter-options';

    // Opción "Seleccionar todo"
    const selectAllOption = createFilterOption('(Seleccionar todo)', '__ALL__', columnIndex);
    optionsContainer.appendChild(selectAllOption);

    // Opciones individuales
    sortedValues.forEach(value => {
        const option = createFilterOption(value, value, columnIndex);
        optionsContainer.appendChild(option);
    });

    dropdown.appendChild(optionsContainer);

    // Posicionar dropdown
    clearHeaderOpenState();
    headerElement.classList.add('is-open');
    dropdown.style.width = `${dropdownWidth}px`;

    document.body.appendChild(dropdown);
    positionFilterDropdown(dropdown, headerElement, dropdownWidth);
    currentFilterDropdown = dropdown;
    currentFilterHeaderEl = headerElement;
    bindFilterDropdownAutoPosition();

    // Marcar checkboxes según filtros activos
    const activeColumnFilter = activeFilters[columnIndex];
    if (activeColumnFilter) {
        const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            const value = checkbox.dataset.value;
            checkbox.checked = activeColumnFilter.includes(value);
            setOptionCheckedStyle(checkbox);
        });
    } else {
        // Por defecto, todos seleccionados
        const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
            setOptionCheckedStyle(checkbox);
        });
    }
}

function positionFilterDropdown(dropdown, headerElement, dropdownWidth) {
    const headerRect = headerElement.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    const minMargin = 10;
    const gap = 8;
    const optionsContainer = dropdown.querySelector('.filter-options');

    let left = headerRect.left;
    if (left + dropdownWidth > viewportWidth - minMargin) {
        left = viewportWidth - dropdownWidth - minMargin;
    }
    if (left < minMargin) {
        left = minMargin;
    }

    const spaceBelow = viewportHeight - headerRect.bottom - gap - minMargin;
    const spaceAbove = headerRect.top - gap - minMargin;

    const contentHeight = Math.ceil(dropdown.scrollHeight || 240);
    const prefersAbove = spaceBelow < 120 && spaceAbove > spaceBelow;
    let openAbove = prefersAbove;

    if (!prefersAbove && contentHeight > spaceBelow && spaceAbove > spaceBelow) {
        openAbove = true;
    }

    const availableHeight = openAbove ? spaceAbove : spaceBelow;
    const safeHeight = Math.max(90, Math.floor(availableHeight));
    if (optionsContainer) {
        const reservedChrome = 22;
        optionsContainer.style.maxHeight = `${Math.max(70, safeHeight - reservedChrome)}px`;
    }

    const panelHeight = Math.ceil(dropdown.offsetHeight || safeHeight);
    let top = openAbove
        ? (headerRect.top - panelHeight - gap)
        : (headerRect.bottom + gap);

    if (top + panelHeight > viewportHeight - minMargin) {
        top = viewportHeight - panelHeight - minMargin;
    }

    if (top < minMargin) {
        top = minMargin;
    }

    const anchorX = Math.round((headerRect.left + (headerRect.width / 2)) - left - 6);
    const arrowMin = 14;
    const arrowMax = Math.max(arrowMin, dropdownWidth - 26);
    const arrowOffset = Math.min(Math.max(anchorX, arrowMin), arrowMax);

    dropdown.style.left = `${Math.round(left)}px`;
    dropdown.style.top = `${Math.round(top)}px`;
    dropdown.style.setProperty('--anchor-offset', `${arrowOffset}px`);
    dropdown.classList.toggle('open-up', openAbove);
}

function repositionCurrentFilterDropdown() {
    if (!currentFilterDropdown || !currentFilterHeaderEl) return;
    const currentWidth = currentFilterDropdown.offsetWidth || parseInt(currentFilterDropdown.style.width || '220', 10);
    positionFilterDropdown(currentFilterDropdown, currentFilterHeaderEl, currentWidth);
}

function bindFilterDropdownAutoPosition() {
    window.addEventListener('resize', repositionCurrentFilterDropdown);
    document.addEventListener('scroll', repositionCurrentFilterDropdown, true);
}

function unbindFilterDropdownAutoPosition() {
    window.removeEventListener('resize', repositionCurrentFilterDropdown);
    document.removeEventListener('scroll', repositionCurrentFilterDropdown, true);
}

function calculateDynamicDropdownWidth(values, headerElement) {
            const allValues = ['(Seleccionar todo)', ...values.map(v => String(v || ''))];
            const longestText = allValues.reduce((max, current) => {
                return current.length > max.length ? current : max;
            }, '');

            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            context.font = '600 13px "Noto Sans"';

            const textWidth = Math.ceil(context.measureText(longestText).width);
            const headerWidth = Math.ceil(headerElement.getBoundingClientRect().width);

            const estimatedWidth = Math.max(
                headerWidth + 28,
                textWidth + 88,
                220
            );

            const maxAllowedByViewport = Math.max(220, window.innerWidth - 24);
            return Math.min(estimatedWidth, 520, maxAllowedByViewport);
        }

    function setOptionCheckedStyle(checkboxElement) {
        const option = checkboxElement.closest('.filter-option');
        if (option) {
            option.classList.toggle('is-checked', checkboxElement.checked);
        }
    }

    function createFilterOption(label, value, columnIndex) {
        const option = document.createElement('div');
        option.className = 'filter-option';

        // Prevenir propagación de click en la opción
        option.addEventListener('click', function (e) {
            e.stopPropagation();
            // Toggle del checkbox cuando se hace clic en la opción
            const checkbox = this.querySelector('input[type="checkbox"]');
            checkbox.checked = !checkbox.checked;

            // Disparar evento change manualmente
            const event = new Event('change', { bubbles: true });
            checkbox.dispatchEvent(event);
        });

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.dataset.value = value;
        checkbox.checked = true;

        // Prevenir propagación en el checkbox mismo
        checkbox.addEventListener('click', function (e) {
            e.stopPropagation();
        });

        // Lógica "Seleccionar todo"
        if (value === '__ALL__') {
            checkbox.addEventListener('change', function (e) {
                e.stopPropagation();
                const dropdown = this.closest('.filter-dropdown');
                const allCheckboxes = dropdown.querySelectorAll('.filter-option:not(:first-child) input[type="checkbox"]');
                allCheckboxes.forEach(cb => {
                    cb.checked = this.checked;
                    setOptionCheckedStyle(cb);
                });
                setOptionCheckedStyle(this);
                applyColumnFilter(columnIndex, dropdown, false);
            });
        } else {
            checkbox.addEventListener('change', function (e) {
                e.stopPropagation();
                const dropdown = this.closest('.filter-dropdown');
                const selectAllCheckbox = dropdown.querySelector('.filter-option:first-child input[type="checkbox"]');
                const allCheckboxes = dropdown.querySelectorAll('.filter-option:not(:first-child) input[type="checkbox"]');
                const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
                selectAllCheckbox.checked = allChecked;
                setOptionCheckedStyle(this);
                setOptionCheckedStyle(selectAllCheckbox);
                applyColumnFilter(columnIndex, dropdown, false);
            });
        }

        const labelSpan = document.createElement('span');
        labelSpan.textContent = label;

        option.appendChild(checkbox);
        option.appendChild(labelSpan);
        setOptionCheckedStyle(checkbox);

        return option;
    }

    function applyColumnFilter(columnIndex, dropdown, closeDropdown = true) {
        const checkboxes = dropdown.querySelectorAll('.filter-option:not(:first-child) input[type="checkbox"]');
        const selectedValues = [];

        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                selectedValues.push(checkbox.dataset.value);
            }
        });

        if (selectedValues.length === checkboxes.length) {
            // Todos seleccionados = sin filtro
            delete activeFilters[columnIndex];
        } else if (selectedValues.length === 0) {
            // Ninguno seleccionado = ocultar todo
            activeFilters[columnIndex] = [];
        } else {
            activeFilters[columnIndex] = selectedValues;
        }

        applyAllFilters();
        updateFilterHeaderStates();

        if (closeDropdown) {
            dropdown.remove();
            currentFilterDropdown = null;
            currentFilterHeaderEl = null;
            unbindFilterDropdownAutoPosition();
            clearHeaderOpenState();
        }
    }

    function clearColumnFilter(columnIndex) {
        delete activeFilters[columnIndex];
        applyAllFilters();
        updateFilterHeaderStates();

        if (currentFilterDropdown) {
            currentFilterDropdown.remove();
            currentFilterDropdown = null;
            currentFilterHeaderEl = null;
            unbindFilterDropdownAutoPosition();
        }
        clearHeaderOpenState();
    }

    function applyAllFilters() {
        const programaSeleccionado = selectPrograma.value;
        const modalidadSeleccionada = selectModalidad.value;

        const table = document.getElementById('informe-titulados-table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'))
            .filter(row => row.id !== 'informe-total-row-titulados' && !row.querySelector('td[colspan]'));

        rows.forEach(row => {

            const programa = row.cells[1]?.textContent.trim();
            const modalidad = row.cells[2]?.textContent.trim();
            const coincidePrograma = !programaSeleccionado || programa === programaSeleccionado;
            const coincideModalidad = !modalidadSeleccionada || modalidad === modalidadSeleccionada;

            if (!coincidePrograma || !coincideModalidad) {
                row.style.display = 'none';
                return;
            }

            let shouldShow = true;
            for (const [columnIndex, allowedValues] of Object.entries(activeFilters)) {
                const cell = row.cells[parseInt(columnIndex)];
                if (cell) {
                    const cellValue = cell.textContent.trim();
                    if (!allowedValues.includes(cellValue)) {
                        shouldShow = false;
                        break;
                    }
                }
            }

            row.style.display = shouldShow ? '' : 'none';
        });

        let totalH = 0, totalM = 0;

        rows.forEach(row => {
            if (row.style.display === 'none') return;
            totalH += parseInt((row.cells[7]?.textContent || '').replace(/,/g, '').trim()) || 0;
            totalM += parseInt((row.cells[8]?.textContent || '').replace(/,/g, '').trim()) || 0;
        });

        // Actualizar fila de totales
        const totalRow = document.getElementById('informe-total-row-titulados');
        if (totalRow) {
            if (totalH + totalM === 0) {
                totalRow.style.display = 'none';
            } else {
                totalRow.style.display = '';
                totalRow.querySelector('.total-h').textContent = totalH.toLocaleString('en-US');
                totalRow.querySelector('.total-m').textContent = totalM.toLocaleString('en-US');
                totalRow.querySelector('.total-g').textContent = (totalH + totalM).toLocaleString('en-US');
            }
        }

        updateFilterHeaderStates();
    }


    /********************************************************************************
     * PARTE 3: MAPEO Y GESTIÓN DE EVENTOS DEL DOM (Originalmente titulados_mapeo.js)
     ********************************************************************************/

    const selectPrograma = document.getElementById('programa');
    const selectModalidad = document.getElementById('modalidad');
    const selectBoleta = document.getElementById('filtro-boleta');
    const selectTipoTitulacion = document.getElementById('filtro-generacion');
    const contenedor = document.getElementById("tabla-edades-seleccion");
    const btnFinalizar = document.getElementById("btn-finalizar-captura");

    console.log('Boton finalizar: ', btnFinalizar);

    if (btnFinalizar) {
        btnFinalizar.style.display = 'none';
    }

    // Select nivel para roles superiores

    const selectNivel = document.getElementById('select-nivel-superior');
    const selectUnidadAcademica = document.getElementById('select-ua-superior');

    if (selectUnidadAcademica) {
        selectUnidadAcademica.disabled = true;
    }

    if (selectModalidad) selectModalidad.disabled = true;
    if (selectBoleta) selectBoleta.disabled = true;
    if (selectTipoTitulacion) selectTipoTitulacion.disabled = true;

    function resetSelect(select, placeholder) {
        if (!select) return;
        select.innerHTML = `<option value="">${placeholder}</option>`;
        select.disabled = true;
    }

    function filtrarPorSelects() {
        const programaSeleccionado = selectPrograma.value;
        const modalidadSeleccionada = selectModalidad.value;
        const table = document.getElementById('informe-titulados-table');
        const tbody = table.querySelector('tbody');

        if (!programaSeleccionado || !modalidadSeleccionada) {
            tbody.innerHTML = `
            <tr>
                <td colspan="10" style="text-align: center; padding: 40px; color: #999;">
                    <div style="font-size: 48px; margin-bottom: 10px;">📋</div>
                    <div>Seleccione un programa y modalidad para mostrar el informe.</div>
                </td>
            </tr>`;
            return;
        }

        const rows = Array.from(tbody.querySelectorAll('tr'))
            .filter(row => row.id !== 'informe-total-row-titulados' && !row.querySelector('td[colspan]'));

        datosFilasFiltrados = datosFilas.filter(f => {
            const coincidePrograma = !programaSeleccionado || f.Nombre_Programa === programaSeleccionado;
            const coincideModalidad = !modalidadSeleccionada || f.Modalidad === modalidadSeleccionada;
            return coincidePrograma && coincideModalidad && f.Titulados !== null;
        });

        console.log('Datos filtrados:', datosFilasFiltrados);

        rows.forEach(row => {
            const programa = row.cells[1]?.textContent.trim();
            const modalidad = row.cells[2]?.textContent.trim();

            const coincidePrograma = !programaSeleccionado || programa === programaSeleccionado;
            const coincideModalidad = !modalidadSeleccionada || modalidad === modalidadSeleccionada;

            row.style.display = (coincidePrograma && coincideModalidad) ? '' : 'none';
        });

        // Recalcular totales
        let totalH = 0, totalM = 0;
        rows.forEach(row => {
            if (row.style.display === 'none') return;
            totalH += parseInt((row.cells[7]?.textContent || '').replace(/,/g, '').trim()) || 0;
            totalM += parseInt((row.cells[8]?.textContent || '').replace(/,/g, '').trim()) || 0;
        });

        const totalRow = document.getElementById('informe-total-row-titulados');
        if (totalRow) {
            if (totalH + totalM === 0) {
                totalRow.style.display = 'none';
            } else {
                totalRow.style.display = '';
                totalRow.querySelector('.total-h').textContent = totalH.toLocaleString('en-US');
                totalRow.querySelector('.total-m').textContent = totalM.toLocaleString('en-US');
                totalRow.querySelector('.total-g').textContent = (totalH + totalM).toLocaleString('en-US');
            }
        }
    }

    // Semaforo de captura 

    function actualizarSemaforoTitulados() {
        const pill = document.getElementById('pestana-semaforo-titulados');
        const semaforoDot = document.getElementById('semaforo-dot-titulados');
        const semaforoTexto = document.getElementById('semaforo-texto-titulados');

        const accionesMultiples = document.getElementById('acciones-multiples-informe');

        if (!selectPrograma.value || !selectModalidad.value) {
            pill.style.display = 'none';
            if (accionesMultiples) accionesMultiples.style.display = 'none';
            return;
        }

        const semaforos = [...new Set(
            datosFilas
                .filter(f => f.Nombre_Programa === selectPrograma.value && f.Modalidad === selectModalidad.value)
                .map(f => f.Id_Semaforo)
        )];

        if (semaforos.length === 0) {
            pill.style.display = 'none';
            if (accionesMultiples) accionesMultiples.style.display = 'none';
            return;
        }

        // Tomar el semáforo de mayor valor (el más avanzado)
        const valor = Math.max(...semaforos);

        const estados = {
            1: { clase: 'semaforo-rojo', texto: 'No Capturado' },
            2: { clase: 'semaforo-amarillo', texto: 'En Proceso De Captura' },
            3: { clase: 'semaforo-verde', texto: 'Captura Finalizada' },
        };

        console.log('Semáforos encontrados para el programa y modalidad seleccionados:', semaforos, 'Valor seleccionado para semáforo:', valor);

        const estado = estados[valor] ?? estados[1];

        pill.className = `pestana-semaforo ${estado.clase}`;
        semaforoDot.className = `semaforo-dot ${estado.clase}`;
        semaforoTexto.textContent = estado.texto;

        // Controlar visibilidad del panel de acciones múltiples
        if (accionesMultiples) {
            if (valor === 3) {
                accionesMultiples.style.display = 'none';
            } else {
                accionesMultiples.style.display = 'flex';
            }
        }

        // Habilitar/Deshabilitar checkbox general de selección
        const selectAllCheckbox = document.getElementById('seleccionar-todas-informe');
        if (selectAllCheckbox) {
            if (valor === 3) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.disabled = true;
                selectAllCheckbox.style.cursor = 'not-allowed';
                selectAllCheckbox.style.opacity = '0.5';
            } else {
                selectAllCheckbox.disabled = false;
                selectAllCheckbox.style.cursor = 'pointer';
                selectAllCheckbox.style.opacity = '1';
            }
        }

        const filtrosSecundarios = document.getElementById('filtros-secundarios');
        const btnFinalizar = document.getElementById('btn-finalizar-captura');

        if (valor === 3) {
            filtrosSecundarios.style.display = 'none';
            if (btnFinalizar) btnFinalizar.disabled = true;
        } else {
            filtrosSecundarios.style.display = 'block';
            if (btnFinalizar) btnFinalizar.disabled = false;
        }
    }

    function llenarSelect(select, opciones) {
        if (!select) return;
        opciones.forEach(opcion => {
            const opt = document.createElement('option');
            opt.value = opcion;
            opt.textContent = opcion;
            select.appendChild(opt);
        });
    }

    if (selectNivel) {
        selectNivel.addEventListener('change', function () {
            const nivelSeleccionado = this.value;

            // Limpiar opciones previas
            selectUnidadAcademica.innerHTML = '<option value="">Seleccione una unidad académica</option>';

            if (!nivelSeleccionado || !unidadesPorNivel[nivelSeleccionado]) {
                selectUnidadAcademica.disabled = true;
                return;
            }

            const unidades = unidadesPorNivel[nivelSeleccionado];

            unidades.forEach(function (unidad) {
                const option = document.createElement('option');
                option.value = unidad.sigla;
                option.textContent = unidad.nombre;
                selectUnidadAcademica.appendChild(option);
            });

            selectUnidadAcademica.disabled = false;
        });
    }

    if (selectPrograma) {
        selectPrograma.addEventListener('change', function () {

            console.log('¡Evento disparado!', this.value);

            const programaSeleccionado = this.value;
            const filtrosSecundarios = document.getElementById('filtros-secundarios');
            const pill = document.getElementById('pestana-semaforo-titulados');

            filtrosSecundarios.style.display = 'none';
            pill.style.display = 'none';

            resetSelect(selectModalidad, '-- Seleccione una Modalidad --');
            resetSelect(selectBoleta, '-- Seleccione Boleta --');
            if (selectBoleta) selectBoleta.disabled = true;
            if (selectTipoTitulacion) selectTipoTitulacion.disabled = true;

            resetSelect(selectTipoTitulacion, '-- Seleccione Tipo de Titulación --');

            if (!programaSeleccionado) {
                return;
            }

            const modalidades = [...new Set(
                datosFilas
                    .filter(f => f.Nombre_Programa === programaSeleccionado)
                    .map(f => f.Modalidad)
            )];

            turnosDisponibles = [...new Set(
                datosFilas
                    .filter(f => f.Nombre_Programa === programaSeleccionado)
                    .map(f => f.Turno)
                    .filter(t => t)
            )];

            console.log('Turnos disponibles:', turnosDisponibles);

            llenarSelect(selectModalidad, modalidades);
            selectModalidad.disabled = false;

            if (typeof actualizarBarraTitulados === 'function') {
                actualizarBarraTitulados();
            }

            filtrarPorSelects();
        });
    }

    if (selectModalidad) {
        selectModalidad.addEventListener('change', function () {
            console.log('Modalidad cambiada:', this.value);

            if (typeof limpiarTabla === 'function') {
                limpiarTabla();
            } else {
                filasTitulados = [];
                renderizarTablaTituladosCaptura();
            }

            resetSelect(selectBoleta, '-- Seleccione Boleta --');
            resetSelect(selectTipoTitulacion, '-- Seleccione Tipo de Titulación --');

            const filtrosSecundarios = document.getElementById('filtros-secundarios');
            const pill = document.getElementById('pestana-semaforo-titulados');

            if (!this.value) {
                filtrosSecundarios.style.display = 'none';
                pill.style.display = 'none';
                return;
            }

            pill.style.display = 'inline-flex';
            filtrosSecundarios.style.display = 'block';
            if (btnFinalizar) btnFinalizar.style.display = 'inline-block';

            llenarSelect(selectBoleta, boletas);
            selectBoleta.disabled = false;

            if (typeof actualizarBarraTitulados === 'function') {
                actualizarBarraTitulados();
            }

            renderizarTablaTitulados(datosFilas);
            filtrarPorSelects();
            actualizarSemaforoTitulados();
        });
    }

    if (selectBoleta) {
        selectBoleta.addEventListener('change', function () {
            resetSelect(selectTipoTitulacion, '-- Seleccione Tipo de Titulación --');

            if (!this.value) return;
            const tipoTitulacion = [...new Set(datosFilas.map(f => f.Tipo_Titulacion))];
            llenarSelect(selectTipoTitulacion, tipoTitulacion);
            selectTipoTitulacion.disabled = false;
        });
    }

    function actualizarBarraTitulados() {
        const headers = document.querySelectorAll('.tabla-matricula-container .tabla-header');

        // Obtener solo Programa y Modalidad
        const selPrograma = document.getElementById('programa');
        const selModalidad = document.getElementById('modalidad');

        let nombrePrograma = '';
        let nombreModalidad = '';

        if (selPrograma && selPrograma.value && selPrograma.selectedOptions.length > 0) {
            nombrePrograma = selPrograma.selectedOptions[0].textContent.trim();
        }
        if (selModalidad && selModalidad.value && selModalidad.selectedOptions.length > 0) {
            nombreModalidad = selModalidad.selectedOptions[0].textContent.trim();
        }

        headers.forEach(header => {

            let contenido = '';

            if (nombrePrograma) {
                contenido += `<span class="header-programa">${nombrePrograma}</span>`;
            }
            if (nombreModalidad) {
                if (nombrePrograma) contenido += ' • '; // Separador
                contenido += `<span class="header-modalidad">${nombreModalidad}</span>`;
            }

            // Si no hay selecciones, mostrar mensaje por defecto
            if (!contenido) {
                contenido = 'Seleccione Programa y Modalidad';
            }

            // Buscar o crear el elemento h3 para el título
            let h3 = header.querySelector('h3');
            if (!h3) {
                h3 = document.createElement('h3');
                header.insertBefore(h3, header.firstChild); // Insertar antes del botón
            }

            h3.innerHTML = contenido;
        });

        console.log('Barra actualizada:', nombrePrograma, nombreModalidad);
    }

    // Inicializar valores autocompletados por el navegador al recargar la página
    function inicializarValoresAutocompletados() {
        if (selectPrograma && selectPrograma.value) {
            console.log('Autocompletado detectado para programa:', selectPrograma.value);
            selectPrograma.dispatchEvent(new Event('change'));
            
            // Esperar un breve instante para que se cargue la modalidad y disparar su evento si tiene valor
            setTimeout(() => {
                if (selectModalidad && selectModalidad.value) {
                    console.log('Autocompletado detectado para modalidad:', selectModalidad.value);
                    selectModalidad.dispatchEvent(new Event('change'));
                }
            }, 100);
        }
        
        if (selectNivel && selectNivel.value) {
            console.log('Autocompletado detectado para nivel:', selectNivel.value);
            selectNivel.dispatchEvent(new Event('change'));
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            inicializarValoresAutocompletados();
            
            // Escuchador para actualizar contador de edades al hacer click en los checkboxes
            document.addEventListener('change', function (e) {
                if (e.target && e.target.classList.contains('checkbox-edad')) {
                    actualizarContadorEdades();
                }
            });
        });
    } else {
        inicializarValoresAutocompletados();
        document.addEventListener('change', function (e) {
            if (e.target && e.target.classList.contains('checkbox-edad')) {
                actualizarContadorEdades();
            }
        });
    }

function cargarFilaParaEditar(programaNombre, modalidadNombre, boletaNombre, tipoTitulacionNombre, edadNombre) {
    const programa = document.getElementById('programa');
    const modalidad = document.getElementById('modalidad');
    const boleta = document.getElementById('filtro-boleta');
    const tipoTitulacion = document.getElementById('filtro-generacion');

    if (!programa || !modalidad || !boleta || !tipoTitulacion) return;

    // Buscar la opción del programa por su texto visible
    let programaOpcion = Array.from(programa.options).find(opt => opt.text.trim() === programaNombre.trim());
    if (programaOpcion) {
        programa.value = programaOpcion.value;
        programa.dispatchEvent(new Event('change'));
    }

    // Esperar un instante a que se carguen las modalidades
    setTimeout(() => {
        let modalidadOpcion = Array.from(modalidad.options).find(opt => opt.text.trim() === modalidadNombre.trim());
        if (modalidadOpcion) {
            modalidad.value = modalidadOpcion.value;
            modalidad.dispatchEvent(new Event('change'));
        }

        // Esperar otro instante a que se carguen las boletas y tipos de titulación
        setTimeout(() => {
            let boletaOpcion = Array.from(boleta.options).find(opt => opt.text.trim() === String(boletaNombre).trim());
            if (boletaOpcion) {
                boleta.value = boletaOpcion.value;
                boleta.dispatchEvent(new Event('change'));
            }

            let tipoOpcion = Array.from(tipoTitulacion.options).find(opt => opt.text.trim() === tipoTitulacionNombre.trim());
            if (tipoOpcion) {
                tipoTitulacion.value = tipoOpcion.value;
                tipoTitulacion.dispatchEvent(new Event('change'));
            }

            // Marcar el checkbox del grupo de edad correspondiente
            const checkboxes = document.querySelectorAll('.checkbox-edad');
            checkboxes.forEach(cb => {
                if (cb.value.trim() === edadNombre.trim() || cb.dataset.nombre.trim() === edadNombre.trim()) {
                    cb.checked = true;
                } else {
                    cb.checked = false; // Desmarcar las otras para centrarse en esta edición
                }
            });
            actualizarContadorEdades();

            // Llamar a agregarFilasTitulados para que suba la fila al capturador
            agregarFilasTitulados();

            // Hacer scroll suave hacia la tabla de captura
            const topElement = document.getElementById('contenedor-matricula-principal') || document.querySelector('.card');
            if (topElement) {
                topElement.scrollIntoView({ behavior: 'smooth' });
            }
            
            // Mostrar una pequeña notificación Toast indicando que se cargó para editar
            if (typeof Swal !== 'undefined') {
                const Toast = Swal.mixin({
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 2000
                });
                Toast.fire({
                    icon: 'success',
                    title: 'Fila cargada arriba para editar'
                });
            }
        }, 150);
    }, 150);
}

// EVENT DELEGATION FOR MULTI-SELECT CHECKBOXES
document.addEventListener('change', function(e) {
    if (e.target && e.target.id === 'seleccionar-todas-informe') {
        const checkboxes = document.querySelectorAll('.seleccionar-fila-informe');
        checkboxes.forEach(cb => {
            if (!cb.disabled) {
                // Solo marcamos/desmarcamos si la fila es visible en base a los filtros
                const row = cb.closest('tr');
                if (row && row.style.display !== 'none') {
                    cb.checked = e.target.checked;
                    
                    // Al seleccionar de forma masiva, también sincronizamos los turnos opuestos
                    const prog = cb.dataset.programa;
                    const mod = cb.dataset.modalidad;
                    const bol = cb.dataset.boleta;
                    const tipo = cb.dataset.tipoTitulacion;
                    const edad = cb.dataset.edad;
                    const turno = cb.dataset.turno;

                    const opposite = Array.from(document.querySelectorAll('.seleccionar-fila-informe'))
                        .find(other => 
                            other !== cb &&
                            other.dataset.programa === prog &&
                            other.dataset.modalidad === mod &&
                            other.dataset.boleta === bol &&
                            other.dataset.tipoTitulacion === tipo &&
                            other.dataset.edad === edad &&
                            other.dataset.turno !== turno
                        );
                    if (opposite && opposite.checked !== cb.checked) {
                        opposite.checked = cb.checked;
                    }
                }
            }
        });
    } else if (e.target && e.target.classList.contains('seleccionar-fila-informe')) {
        const cb = e.target;
        const isChecked = cb.checked;

        const prog = cb.dataset.programa;
        const mod = cb.dataset.modalidad;
        const bol = cb.dataset.boleta;
        const tipo = cb.dataset.tipoTitulacion;
        const edad = cb.dataset.edad;
        const turno = cb.dataset.turno;

        // Buscar fila con el turno opuesto
        const opposite = Array.from(document.querySelectorAll('.seleccionar-fila-informe'))
            .find(other => 
                other !== cb &&
                other.dataset.programa === prog &&
                other.dataset.modalidad === mod &&
                other.dataset.boleta === bol &&
                other.dataset.tipoTitulacion === tipo &&
                other.dataset.edad === edad &&
                other.dataset.turno !== turno
            );

        if (opposite && opposite.checked !== isChecked) {
            opposite.checked = isChecked;
        }

        // Actualizar estado del checkbox "Seleccionar todas" (solo considerando visibles)
        const selectAll = document.getElementById('seleccionar-todas-informe');
        if (selectAll) {
            const visibleCheckboxes = Array.from(document.querySelectorAll('.seleccionar-fila-informe'))
                .filter(c => {
                    const row = c.closest('tr');
                    return row && row.style.display !== 'none';
                });
            const allChecked = visibleCheckboxes.length > 0 && visibleCheckboxes.every(c => c.checked);
            selectAll.checked = allChecked;
        }
    }
});

function editarFilasSeleccionadas() {
    const selected = document.querySelectorAll('.seleccionar-fila-informe:checked');
    if (selected.length === 0) {
        Swal.fire({
            icon: 'warning',
            title: 'Sin selección',
            text: 'Por favor, seleccione al menos una fila del informe para editar.',
            confirmButtonColor: '#750946'
        });
        return;
    }

    Swal.fire({
        title: '¿Cargar registros seleccionados?',
        text: 'Se cargarán los registros para su edición.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#17a2b8',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, cargar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            // Limpiar la captura actual antes de cargar las seleccionadas
            filasTitulados = [];
            const keysProcesadas = new Set();

            selected.forEach(cb => {
                const progName = decodeURIComponent(cb.dataset.programa);
                const modName = decodeURIComponent(cb.dataset.modalidad);
                const bolName = decodeURIComponent(cb.dataset.boleta);
                const tipoName = decodeURIComponent(cb.dataset.tipoTitulacion);
                const edadVal = decodeURIComponent(cb.dataset.edad);
                const ramName = decodeURIComponent(cb.dataset.rama);

                const claveFila = `${progName}|${modName}|${bolName}|${tipoName}|${edadVal}`;
                if (keysProcesadas.has(claveFila)) {
                    return; // Ya procesamos este registro (del turno opuesto)
                }
                keysProcesadas.add(claveFila);

                // Buscar los turnos guardados para esta fila en datosFilas
                const turnosDeFila = [...new Set(
                    datosFilas
                        .filter(d => 
                            d &&
                            d.Nombre_Programa === progName &&
                            d.Modalidad === modName &&
                            String(d.Boleta) === String(bolName) &&
                            d.Tipo_Titulacion === tipoName &&
                            d.Grupo_Edad === edadVal
                        )
                        .map(d => d.Turno)
                )];

                const turnosUsar = turnosDeFila.length > 0 ? turnosDeFila : ['Matutino', 'Vespertino'];

                const turnosObj = {};
                turnosUsar.forEach(turno => {
                    // Buscar si existe registro guardado para este turno en versión HOMBRE
                    const registroHombre = datosFilas.find(d =>
                        d &&
                        d.Nombre_Programa === progName &&
                        d.Modalidad === modName &&
                        String(d.Boleta) === String(bolName) &&
                        d.Tipo_Titulacion === tipoName &&
                        d.Grupo_Edad === edadVal &&
                        d.Turno === turno &&
                        (d.Sexo === 'Hombre' || d.Sexo === 'H' || d.Sexo === 'HOMBRE')
                    );

                    // Buscar si existe registro guardado para este turno en versión MUJER
                    const registroMujer = datosFilas.find(d =>
                        d &&
                        d.Nombre_Programa === progName &&
                        d.Modalidad === modName &&
                        String(d.Boleta) === String(bolName) &&
                        d.Tipo_Titulacion === tipoName &&
                        d.Grupo_Edad === edadVal &&
                        d.Turno === turno &&
                        (d.Sexo === 'Mujer' || d.Sexo === 'M' || d.Sexo === 'MUJER')
                    );

                    turnosObj[turno] = {
                        hombres: registroHombre ? registroHombre.Titulados : '',
                        mujeres: registroMujer ? registroMujer.Titulados : ''
                    };
                });

                // Buscar boleta y tipoTitulacion ids desde los selectores si coinciden por texto
                const selectBoleta = document.getElementById('filtro-boleta');
                let bolVal = bolName;
                if (selectBoleta) {
                    const opt = Array.from(selectBoleta.options).find(o => o.text.trim() === bolName.trim());
                    if (opt) bolVal = opt.value;
                }

                const selectTipo = document.getElementById('filtro-generacion');
                let tipoVal = tipoName;
                if (selectTipo) {
                    const opt = Array.from(selectTipo.options).find(o => o.text.trim() === tipoName.trim());
                    if (opt) tipoVal = opt.value;
                }

                filasTitulados.push({
                    id: Date.now() + Math.random(),
                    programa: selectPrograma.value,
                    programaNombre: progName,
                    modalidad: selectModalidad.value,
                    modalidadNombre: modName,
                    boleta: bolVal,
                    boletaNombre: bolName,
                    tipoTitulacion: tipoVal,
                    tipoTitulacionNombre: tipoName,
                    edad: edadVal,
                    edadNombre: edadVal,
                    ramaNombre: ramName,
                    turnos: turnosObj
                });
            });

            // Generar cabecera y renderizar
            generarCabeceraTabla();
            renderizarTablaTituladosCaptura();

            // Scroll suave
            const topElement = document.getElementById('contenedor-matricula-principal') || document.querySelector('.card');
            if (topElement) {
                topElement.scrollIntoView({ behavior: 'smooth' });
            }

            // Desmarcar todos los checkboxes
            selected.forEach(cb => cb.checked = false);
            const selectAll = document.getElementById('seleccionar-todas-informe');
            if (selectAll) selectAll.checked = false;

            Swal.fire({
                icon: 'success',
                title: 'Registros cargados',
                text: `${keysProcesadas.size} registros cargados para editar.`,
                timer: 2000,
                showConfirmButton: false
            });
        }
    });
}

function borrarFilasSeleccionadas() {
    const selected = document.querySelectorAll('.seleccionar-fila-informe:checked');
    if (selected.length === 0) {
        Swal.fire({
            icon: 'warning',
            title: 'Sin selección',
            text: 'Por favor, seleccione al menos una fila del informe para eliminar.',
            confirmButtonColor: '#750946'
        });
        return;
    }

    const keysProcesadas = new Set();
    selected.forEach(cb => {
        const progName = decodeURIComponent(cb.dataset.programa);
        const modName = decodeURIComponent(cb.dataset.modalidad);
        const bolName = decodeURIComponent(cb.dataset.boleta);
        const tipoName = decodeURIComponent(cb.dataset.tipoTitulacion);
        const edadVal = decodeURIComponent(cb.dataset.edad);
        const claveFila = `${progName}|${modName}|${bolName}|${tipoName}|${edadVal}`;
        keysProcesadas.add(claveFila);
    });

    Swal.fire({
        title: '⚠️ ¿Está seguro de eliminar los registros seleccionados?',
        text: `Se establecerán a cero los valores de hombres y mujeres para los ${keysProcesadas.size} registros seleccionados en la base de datos.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            // Limpiar y preparar filasTitulados con todos los registros seleccionados en 0
            filasTitulados = [];
            const keysAgregadas = new Set();

            selected.forEach(cb => {
                const progName = decodeURIComponent(cb.dataset.programa);
                const modName = decodeURIComponent(cb.dataset.modalidad);
                const bolName = decodeURIComponent(cb.dataset.boleta);
                const tipoName = decodeURIComponent(cb.dataset.tipoTitulacion);
                const edadVal = decodeURIComponent(cb.dataset.edad);
                const ramName = decodeURIComponent(cb.dataset.rama);

                const claveFila = `${progName}|${modName}|${bolName}|${tipoName}|${edadVal}`;
                if (keysAgregadas.has(claveFila)) {
                    return; // Ya agregamos este registro
                }
                keysAgregadas.add(claveFila);

                const turnosDeFila = [...new Set(
                    datosFilas
                        .filter(d => 
                            d &&
                            d.Nombre_Programa === progName &&
                            d.Modalidad === modName &&
                            String(d.Boleta) === String(bolName) &&
                            d.Tipo_Titulacion === tipoName &&
                            d.Grupo_Edad === edadVal
                        )
                        .map(d => d.Turno)
                )];

                const turnosUsar = turnosDeFila.length > 0 ? turnosDeFila : ['Matutino', 'Vespertino'];

                const turnosObj = {};
                turnosUsar.forEach(turno => {
                    turnosObj[turno] = { hombres: 0, mujeres: 0 };
                });

                filasTitulados.push({
                    id: Date.now() + Math.random(),
                    programa: "",
                    programaNombre: progName,
                    modalidad: "",
                    modalidadNombre: modName,
                    boleta: String(bolName),
                    boletaNombre: String(bolName),
                    tipoTitulacion: "",
                    tipoTitulacionNombre: tipoName,
                    edad: edadVal,
                    edadNombre: edadVal,
                    ramaNombre: ramName,
                    turnos: turnosObj
                });
            });

            // Llamar a guardarAvance indicando que es una eliminación
            guardarAvance(true);
        }
    });
}

// Restricción global para inputs de captura numérica (4 dígitos, sin signos ni puntos)
document.addEventListener('keydown', function(e) {
    if (e.target && e.target.type === 'number' && e.target.closest('#tabla-titulados-body, .tabla-matricula-container, .capture-table')) {
        if (['-', '.', '+', 'e', 'E', ','].includes(e.key)) {
            e.preventDefault();
        }
    }
}, true);

document.addEventListener('input', function(e) {
    if (e.target && e.target.type === 'number' && e.target.closest('#tabla-titulados-body, .tabla-matricula-container, .capture-table')) {
        const clean = e.target.value.replace(/[^0-9]/g, '').slice(0, 4);
        if (e.target.value !== clean) {
            e.target.value = clean;
        }
    }
}, true);

document.addEventListener('paste', function(e) {
    if (e.target && e.target.type === 'number' && e.target.closest('#tabla-titulados-body, .tabla-matricula-container, .capture-table')) {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData('text') || '';
        const clean = text.replace(/[^0-9]/g, '').slice(0, 4);
        e.target.value = clean;
        e.target.dispatchEvent(new Event('input', { bubbles: true }));
        e.target.dispatchEvent(new Event('change', { bubbles: true }));
    }
}, true);

