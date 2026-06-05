const selectPrograma = document.getElementById('programa');
const selectModalidad = document.getElementById('modalidad');
const selectBoleta = document.getElementById('filtro-boleta');
const selectTipoTitulacion = document.getElementById('filtro-generacion');
const contenedor = document.getElementById("tabla-edades-seleccion");

selectModalidad.disabled = true;
selectBoleta.disabled = true;
selectTipoTitulacion.disabled = true;

function resetSelect(select, placeholder) {
    select.innerHTML = `<option value="">${placeholder}</option>`;
    select.disabled = true;
}

// Tu función de filtrado — solo esta es nueva
function filtrarPorSelects() {
    const programaSeleccionado = selectPrograma.value;
    const modalidadSeleccionada = selectModalidad.value;

    const table = document.getElementById('informe-titulados-table');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'))
        .filter(row => !row.querySelector('td[colspan]'));

    rows.forEach(row => {
        const programa  = row.cells[0]?.textContent.trim();
        const modalidad = row.cells[1]?.textContent.trim();

        const coincidePrograma  = !programaSeleccionado  || programa  === programaSeleccionado;
        const coincideModalidad = !modalidadSeleccionada || modalidad === modalidadSeleccionada;

        row.style.display = (coincidePrograma && coincideModalidad) ? '' : 'none';
    });

    // Recalcular totales
    let totalH = 0, totalM = 0;
    rows.forEach(row => {
        if (row.style.display === 'none') return;
        totalH += parseInt(row.cells[6]?.textContent.trim()) || 0;
        totalM += parseInt(row.cells[7]?.textContent.trim()) || 0;
    });

    const totalRow = document.getElementById('informe-total-row-titulados');
    if (totalRow) {
        if (totalH + totalM === 0) {
            totalRow.style.display = 'none';
        } else {
            totalRow.style.display = '';
            totalRow.querySelector('.total-h').textContent = totalH;
            totalRow.querySelector('.total-m').textContent = totalM;
            totalRow.querySelector('.total-g').textContent = totalH + totalM;
        }
    }
}

function llenarSelect(select, opciones) {
    opciones.forEach(opcion => {
        const opt = document.createElement('option');
        opt.value = opcion;
        opt.textContent = opcion;
        select.appendChild(opt);
    });
}

selectPrograma.addEventListener('change', function() {
    const programaSeleccionado = this.value;
    const filtrosSecundarios = document.getElementById('filtros-secundarios');

    filtrosSecundarios.style.display = 'none';

    resetSelect(selectModalidad, '-- Seleccione una Modalidad --');
    resetSelect(selectBoleta, '-- Seleccione Boleta --');
    selectBoleta.disabled = true;
    selectTipoTitulacion.disabled = true;

    resetSelect(selectTipoTitulacion, '-- Seleccione Tipo de Titulación --');

    if (!programaSeleccionado) return;

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

selectModalidad.addEventListener('change', function() {
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

    if (!this.value) {
        filtrosSecundarios.style.display = 'none';
        return;
    }

    filtrosSecundarios.style.display = 'block'; 

    llenarSelect(selectBoleta, boletas);
    selectBoleta.disabled = false;

    if (typeof actualizarBarraTitulados === 'function') {
        actualizarBarraTitulados();
    }

    filtrarPorSelects();

});

selectBoleta.addEventListener('change', function() {
    //const boletaSeleccionada = this.value;
    
    resetSelect(selectTipoTitulacion, '-- Seleccione Tipo de Titulación --');

    
    if (!this.value) return;
    const tipoTitulacion = [...new Set(datosFilas.map(f => f.Tipo_Titulacion))];
    llenarSelect(selectTipoTitulacion, tipoTitulacion);
    selectTipoTitulacion.disabled = false;
});
/*
selectTipoTitulacion.addEventListener('change', function() {

    resetSelect(selectTurno, '-- Seleccione Turno --');

    if (!this.value) return;
    const turno = [...new Set(datosFilas.map(f => f.Turno))];
       
    llenarSelect(selectTurno, turno);
    selectTurno.disabled = false;
});*/

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
            //h3.style.margin = '0';
            //h3.style.fontSize = '18px';
            //h3.style.fontWeight = '600';
            header.insertBefore(h3, header.firstChild); // Insertar antes del botón
        }
        
        h3.innerHTML = contenido;
    });
    
    console.log('Barra actualizada:', nombrePrograma, nombreModalidad);
}


