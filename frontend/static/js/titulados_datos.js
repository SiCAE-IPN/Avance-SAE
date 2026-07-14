
function actualizarValorFila(idFila, campo, valor) {

    const numero = valor === "" ? 0 : Math.max(0, Number(valor));

    const fila = filasTitulados.find(f => f.id === idFila);

    if (fila) {
        fila[campo] = numero;
    }

    console.log("Filas actualizadas:", filasTitulados);
}

function guardarAvance() {
    fetch('/titulados/guardar-avance-titulados', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(filasTitulados)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Error en la respuesta del servidor');
        }
        return response.json();
    })
    .then(data => {
        console.log('Respuesta del servidor:', data);
        alert('Avance guardado correctamente');
        
        window.location.reload();  
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error al guardar el avance, por favor intente de nuevo.');
    });
    
}

//Finalizar Captura

function finalizarCapturaTitulados() {

    const programa = document.getElementById('programa').value;
    const modalidad = document.getElementById('modalidad').value;

    if (!programa || programa === "" || programa === "0") {
        alert("Por favor selecciona un programa.");
        return;
    }

    if (!modalidad || modalidad === "" || modalidad === "0") {
        alert("Por favor selecciona una modalidad.");
        return;
    }

    fetch('/titulados/finalizar-titulados', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            datos: filasTitulados.length > 0 ? filasTitulados : datosFilasFiltrados,
            programa: programa,
            modalidad: modalidad,
            origen: filasTitulados.length > 0 ? "captura" : "db"  // ← aquí
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Error en la respuesta del servidor');
        return response.json();
    })
    .then(data => {
        console.log('Respuesta del servidor:', data);
        alert('Finalizado programa modalidad correctamente');
        window.location.reload();
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error al finalizar programa modalidad, por favor intente de nuevo.');
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
                Modalidad:       fila.Modalidad,
                Turno:           fila.Turno,
                Boleta:          fila.Boleta,
                Tipo_Titulacion: fila.Tipo_Titulacion,
                Grupo_Edad:      fila.Grupo_Edad,
                Hombres:         0,
                Mujeres:         0,
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
    if (!datosFilas || datosFilas.length === 0) return;

    // Agrupar antes de renderizar
    const filas = agruparPorSexo(datosFilas);

    tbody.innerHTML = '';

    if (filas.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 30px; color: #999;">
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
        html += `<tr style="background: ${i % 2 === 0 ? '#f9f9f9' : 'white'}">
            <td style="padding:10px; border:1px solid #ddd;">${fila.Nombre_Programa}</td>
            <td style="padding:10px; border:1px solid #ddd;">${fila.Modalidad}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Turno}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Boleta}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Tipo_Titulacion}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Grupo_Edad}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Hombres}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd;">${fila.Mujeres}</td>
            <td style="padding:10px; text-align:center; border:1px solid #ddd; font-weight:700;">${total}</td>
        </tr>`;
    });

    html += `<tr id="informe-total-row-titulados" style="background: linear-gradient(135deg, #750946 0%, #a3195b 100%); color:white; font-weight:700;">
        <td colspan="6" style="padding:12px; border:1px solid #ddd; text-align:right;">TOTAL GENERAL:</td>
        <td class="total-h" style="padding:12px; text-align:center; border:1px solid #ddd;">${totalGeneralH}</td>
        <td class="total-m" style="padding:12px; text-align:center; border:1px solid #ddd;">${totalGeneralM}</td>
        <td class="total-g" style="padding:12px; text-align:center; font-size:18px;">${totalGeneralH + totalGeneralM}</td>
    </tr>`;

    tbody.innerHTML = html;
}


// Filtros de resumen


function initTableFilters() {


    const headers = document.querySelectorAll('.filterable-header');
    updateFilterHeaderStates();
    
    headers.forEach(header => {
        header.addEventListener('click', function(e) {
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
        .filter(row => !row.querySelector('td[colspan]'))
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
        return a.localeCompare(b, 'es', {numeric: true});
    });

    const dropdownWidth = calculateDynamicDropdownWidth(sortedValues, headerElement);
    
    // Crear dropdown
    const dropdown = document.createElement('div');
    dropdown.className = 'filter-dropdown active';
    dropdown.dataset.column = columnIndex;
    
    // Prevenir que clicks dentro del dropdown lo cierren
    dropdown.addEventListener('click', function(e) {
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
    option.addEventListener('click', function(e) {
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
    checkbox.addEventListener('click', function(e) {
        e.stopPropagation();
    });
    
    // Lógica "Seleccionar todo"
    if (value === '__ALL__') {
        checkbox.addEventListener('change', function(e) {
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
        checkbox.addEventListener('change', function(e) {
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
        .filter(row => !row.querySelector('td[colspan]'));

    rows.forEach(row => {
        
        const programa  = row.cells[0]?.textContent.trim();
        const modalidad = row.cells[1]?.textContent.trim();
        const coincidePrograma  = !programaSeleccionado  || programa  === programaSeleccionado;
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
        totalH += parseInt(row.cells[6]?.textContent.trim()) || 0;
        totalM += parseInt(row.cells[7]?.textContent.trim()) || 0;
    });

    // Actualizar fila de totales
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

    updateFilterHeaderStates();
}