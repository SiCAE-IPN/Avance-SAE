
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
        const turnosObj = {};
        
        turnosDisponibles.forEach(turno => {
            // Buscamos si existe registro guardado para este turno en versión HOMBRE
            const registroHombre = datosFilas.find(d => 
                d.Nombre_Programa === programa.options[programa.selectedIndex].text &&
                d.Modalidad === modalidad.options[modalidad.selectedIndex].text &&
                String(d.Boleta) === String(boleta.options[boleta.selectedIndex].text) &&
                d.Tipo_Titulacion === tipoTitulacion.options[tipoTitulacion.selectedIndex].text &&
                d.Grupo_Edad === edadNombre &&
                d.Turno === turno &&
                d.Sexo === 'Hombre'
            );

            // Buscamos si existe registro guardado para este turno en versión MUJER
            const registroMujer = datosFilas.find(d => 
                d.Nombre_Programa === programa.options[programa.selectedIndex].text &&
                d.Modalidad === modalidad.options[modalidad.selectedIndex].text &&
                String(d.Boleta) === String(boleta.options[boleta.selectedIndex].text) &&
                d.Tipo_Titulacion === tipoTitulacion.options[tipoTitulacion.selectedIndex].text &&
                d.Grupo_Edad === edadNombre &&
                d.Turno === turno &&
                d.Sexo === 'Mujer'
            );

            // Asignamos el valor encontrado en la BD, o un string vacío si no hay antecedentes
            turnosObj[turno] = {
                hombres: registroHombre ? registroHombre.Titulados : '',
                mujeres: registroMujer ? registroMujer.Titulados : ''
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

    fila1 += '<th rowspan="2" style="padding:12px 15px; text-align:center; font-weight:600; font-size:14px; border:1px solid rgba(255,255,255,0.2); vertical-align:middle;">Acciones</th>';
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

    const colspan = 3 + turnosDisponibles.length * 2 + 1;

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
                    <input type="number" min="0"
                        value="${vals.hombres}"
                        onkeydown="if(event.key==='-'||event.key==='.'||event.key==='e') event.preventDefault()"
                        oninput="this.value=this.value.replace(/[^0-9]/g,'').slice(0,4); actualizarValorTitulado(${fila.id}, '${turno}', 'hombres', this.value)"
                        style="width:42px;padding:2px 3px;border:2px solid #2196f3;border-radius:3px;background:#fff;color:#1976d2;font-weight:600;text-align:center;font-size:11px;">
                </div>
            </td>
            <td style="padding:8px; text-align:center;">
                <div style="display:inline-flex;align-items:center;gap:3px;padding:2px 4px;background:#fce4ec;border-radius:4px;border:1px solid #f48fb1;line-height:1;">
                    <div style="font-weight:700;color:#c2185b;font-size:11px;min-width:14px;text-align:center;">M</div>
                    <input type="number" min="0"
                        value="${vals.mujeres}"
                        onkeydown="if(event.key==='-'||event.key==='.'||event.key==='e') event.preventDefault()"
                        oninput="this.value=this.value.replace(/[^0-9]/g,'').slice(0,4); actualizarValorTitulado(${fila.id}, '${turno}', 'mujeres', this.value)"
                        style="width:42px;padding:2px 3px;border:2px solid #e91e63;border-radius:3px;background:#fff;color:#c2185b;font-weight:600;text-align:center;font-size:11px;">
                </div>
            </td>`;
        });

        celdas += `
            <td style="padding:12px; text-align:center;">
                <button type="button"
                        onclick="eliminarFilaTitulado(${fila.id})"
                        style="padding:6px 12px;background:#dc3545;color:white;border:none;border-radius:4px;cursor:pointer;font-size:14px;"
                        title="Eliminar fila">🗑️</button>
            </td>`;

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

function eliminarFilaEgresado(id) {
    if (confirm('¿Está seguro de eliminar este registro?')) {
        filasTitulados = filasTitulados.filter(f => f.id !== id);
        renderizarTablaTituladosCaptura();
       
    }
}


function limpiarTabla() {
    
    if (filasTitulados.length > 0  && confirm(`¿Está seguro de eliminar los ${filasTitulados.length} registros?`)) {
        filasTitulados = [];
        renderizarTablaTituladosCaptura();
        console.log('Tabla limpiada completamente');
    }
}



document.addEventListener('DOMContentLoaded', function () {

    const btnConsultar = document.getElementById('btn-ver-resumen-director');
    
    const selectPeriodo = document.getElementById('select-periodo-director');
    const selectNivel   = document.getElementById('select-nivel-director');

    const selectPeriodoSuperior = document.getElementById('select-periodo-superior');
    const selectNivelSuperior   = document.getElementById('select-nivel-superior');
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
    if(btnConsultar){
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
