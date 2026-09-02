// ==========================================
// 1. Variables Globales y Estado
// ==========================================
let semestreActual = 0;
let maxSemestres = 0;
let turnosEnPantalla = [];
let cambiosGlobales = {};
let scrollPendiente = null;


let estadosSemaforoPorSemestre = {};
let semestresDisponiblesSP = [];
const SEMAFORO_COLORES = {
    1: { color: '#d32f2f', descripcion: 'Sin Datos' },
    2: { color: '#f57c00', descripcion: 'Datos Parciales' },
    3: { color: '#2e7d32', descripcion: 'Datos Completos' }
};

// Variables de estado de validación (se inyectan desde el template)
let usuario_ya_valido = false;
let usuario_ya_rechazo = false;
let validacionMasivaEnCurso = false;

// ==========================================
// 2. Funciones de Utilidad
// ==========================================
function normalizarSemestre(semestre) {
    if (typeof semestre === 'number') return semestre;
    const mapa = {
        'primer': 1, 'primero': 1, 'segundo': 2, 'tercer': 3, 'tercero': 3,
        'cuarto': 4, 'quinto': 5, 'sexto': 6, 'septimo': 7,
        'octavo': 8, 'noveno': 9, 'decimo': 10
    };
    const texto = String(semestre).toLowerCase().trim()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    return mapa[texto] ?? parseInt(texto, 10);
}

function semestreNumeroATexto(num) {
    const mapaInverso = {
        1: 'Primero', 2: 'Segundo', 3: 'Tercero', 4: 'Cuarto',
        5: 'Quinto',  6: 'Sexto',   7: 'Septimo', 8: 'Octavo',
        9: 'Noveno',  10: 'Decimo'
    };
    return mapaInverso[num] || num.toString();
}

// ==========================================
// 3. Semaforo
// ==========================================
function procesarEstadosSemaforoAprovechamiento(prog, mod) {
    estadosSemaforoPorSemestre = {};
    semestresDisponiblesSP = [];
    if (!window.aprovechamientos) return;

    const progNorm = String(prog).trim().toUpperCase();
    const modNorm  = String(mod).trim().toUpperCase();
    const semSet   = new Set();

    window.aprovechamientos.forEach(r => {
        const rProg = String(r.Nombre_Programa || '').trim().toUpperCase();
        const rMod  = String(r.Modalidad || '').trim().toUpperCase();
        if (rProg !== progNorm || rMod !== modNorm) return;

        const sem     = normalizarSemestre(r.Semestre || r.semestre);
        const idSemaf = r.Id_Semaforo ?? r.id_semaforo ?? 1;
        if (!isNaN(sem) && sem > 0) {
            semSet.add(sem);
            const actual = estadosSemaforoPorSemestre[sem] ?? 0;
            if (idSemaf > actual) estadosSemaforoPorSemestre[sem] = idSemaf;
        }
    });

    semestresDisponiblesSP = Array.from(semSet).sort((a, b) => a - b);
}

function actualizarColorPestana(tab, semestreNum) {
    const idSem = estadosSemaforoPorSemestre[semestreNum] ?? 1;
    const info  = SEMAFORO_COLORES[idSem] || SEMAFORO_COLORES[1];
    tab.classList.remove('semaforo-estado-1', 'semaforo-estado-2', 'semaforo-estado-3');
    tab.classList.add(`semaforo-estado-${idSem}`);
    tab.title = info.descripcion;
    tab.style.backgroundColor = '';
}

function actualizarColoresPestanas() {
    document.querySelectorAll('.semestre-tab').forEach(tab => {
        const sem = parseInt(tab.getAttribute('data-semestre'));
        if (!isNaN(sem)) actualizarColorPestana(tab, sem);
    });
}

// ==========================================
// 4. Pestañas de semestres
// ==========================================
window.cargarSemestresTabs = function (prog, mod, semForzado = null) {
    const container = document.getElementById('semestres-tabs');
    if (!container) return;
    container.innerHTML = '';

    if (!window.aprovechamientos) return;

    procesarEstadosSemaforoAprovechamiento(prog, mod);

    if (semestresDisponiblesSP.length === 0) {
        const tbody = document.getElementById('tabla-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:40px;">No hay semestres disponibles para esta combinación</td></tr>';
        // Ocultar contenedor de captura
        const capturaContainer = document.getElementById('captura-matricula-container');
        if (capturaContainer) capturaContainer.style.display = 'none';
        return;
    }

    // Mostrar el contenedor de captura ahora que hay datos
    const capturaContainer = document.getElementById('captura-matricula-container');
    if (capturaContainer) capturaContainer.style.display = 'block';

    maxSemestres = semestresDisponiblesSP[semestresDisponiblesSP.length - 1];

    if (semForzado !== null && semestresDisponiblesSP.includes(Number(semForzado))) {
        semestreActual = Number(semForzado);
    } else {
        semestreActual = semestresDisponiblesSP[0];
    }

    actualizarBarraSemestreActual(semestreActual);

    const fragment = document.createDocumentFragment();
    semestresDisponiblesSP.forEach(sem => {
        const tab = document.createElement('button');
        tab.className = 'semestre-tab';
        tab.textContent = `Semestre ${sem}`;
        tab.setAttribute('data-semestre', sem);
        actualizarColorPestana(tab, sem);
        if (sem === semestreActual) tab.classList.add('active');
        fragment.appendChild(tab);
    });

    container.appendChild(fragment);

    container.onclick = function (e) {
        const tab = e.target.closest('.semestre-tab');
        if (!tab) return;
        const sem = parseInt(tab.getAttribute('data-semestre'));
        if (!isNaN(sem)) seleccionarSemestre(sem);
    };

    window.cargarTablaAprovechamiento(prog, mod, semestreActual);
};

// ==========================================
// 5. Seleccionar Semestre
// ==========================================
function seleccionarSemestre(sem) {
    const prog = document.getElementById('programa')?.value;
    const mod  = document.getElementById('modalidad')?.value;
    if (!prog || !mod) return;

    semestreActual = sem;

    document.querySelectorAll('.semestre-tab').forEach(tab => {
        const tabSem = parseInt(tab.getAttribute('data-semestre'));
        tab.classList.toggle('active', tabSem === sem);
    });

    actualizarBarraSemestreActual(sem);

    setTimeout(() => {
        const cont = document.querySelector('.tabla-matricula-container');
        if (cont) {
            const rect = cont.getBoundingClientRect();
            window.scrollTo({ top: window.pageYOffset + rect.top - 150, behavior: 'smooth' });
        }
    }, 200);

    window.cargarTablaAprovechamiento(prog, mod, sem);
}

// ==========================================
// 6. Barra de semestre actual
// ==========================================
function actualizarBarraSemestreActual(semestreNum) {
    const headers    = document.querySelectorAll('.tabla-matricula-container .tabla-header');
    const nombreProg = document.getElementById('programa')?.selectedOptions?.[0]?.textContent?.trim() || '';
    const nombreMod  = document.getElementById('modalidad')?.selectedOptions?.[0]?.textContent?.trim() || '';

    headers.forEach(header => {
        let contenido = `<span class="header-semestre">Semestre ${semestreNum}</span>`;
        if (nombreProg) contenido += `<span class="header-separador"> ◉ </span><span class="header-programa">${nombreProg}</span>`;
        if (nombreMod)  contenido += `<span class="header-separador"> ◉ </span><span class="header-modalidad">${nombreMod}</span>`;
        header.innerHTML = `<h3>${contenido}</h3>`;

        const h3 = header.querySelector('h3');
        if (h3) {
            let fs = 22;
            h3.style.fontSize = fs + 'px';
            while (h3.scrollWidth > header.clientWidth && fs > 11) {
                fs -= 0.5;
                h3.style.fontSize = fs + 'px';
            }
        }
    });
}

// ==========================================
// 7. Encabezado de la tabla
// ==========================================
function renderizarEncabezadoTabla(turnos) {
    const thead = document.getElementById('tabla-header');
    if (!thead) return;
    thead.innerHTML = '';

    const row1 = document.createElement('tr');
    row1.style.background = 'linear-gradient(135deg, #750946 0%, #8B0A4A 100%)';
    row1.style.color = 'white';

    const thSit = document.createElement('th');
    thSit.textContent = 'Situación Académica';
    Object.assign(thSit.style, {
        verticalAlign: 'middle',
        textAlign: 'center',
        padding: '18px 12px',
        fontWeight: '700',
        fontSize: '15px',
        whiteSpace: 'normal',
        wordBreak: 'keep-all',
        borderRight: '3px solid rgba(255,255,255,0.5)',
        minWidth: '160px',
        width: '160px'
    });
    row1.appendChild(thSit);

    turnos.forEach(t => {
        const thT = document.createElement('th');
        thT.textContent = t;
        Object.assign(thT.style, {
            textAlign: 'center',
            padding: '18px 8px',
            fontWeight: '700',
            fontSize: '18px',
            borderRight: '3px solid rgba(255,255,255,0.5)',
            whiteSpace: 'nowrap'
        });
        row1.appendChild(thT);
    });

    thead.appendChild(row1);
}

// ==========================================
// 8. Renderizado principal de la tabla
// ==========================================
window.cargarTablaAprovechamiento = function (programa, modalidad, semestre) {
    const thead = document.getElementById('tabla-header');
    const tbody = document.getElementById('tabla-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (thead) thead.innerHTML = '';

    const prog = String(programa).trim().toUpperCase();
    const mod  = String(modalidad).trim().toUpperCase();
    const sem  = Number(semestre);

    const idSemaforo          = estadosSemaforoPorSemestre[sem] ?? 1;
    const esSemestreBloqueado = (idSemaforo === 3);

    const btnGuardar = document.getElementById('btn-guardar-matricula');
    const btnValidar = document.getElementById('btn-validar-matricula');

    if (btnGuardar) {
        btnGuardar.disabled      = esSemestreBloqueado;
        btnGuardar.style.display = esSemestreBloqueado ? 'none' : 'inline-block';
        btnGuardar.innerHTML     = esSemestreBloqueado ? '🔒 Finalizado' : '💾 Guardar Avance';
        btnGuardar.className     = esSemestreBloqueado ? 'btn btn-secondary' : 'btn btn-primary';
    }
    if (btnValidar) {
        btnValidar.disabled  = esSemestreBloqueado;
        btnValidar.innerHTML = esSemestreBloqueado ? '✅ Semestre Validado' : '✅ Finalizar Captura';
        if (esSemestreBloqueado) {
            btnValidar.classList.remove('btn-primary', 'btn-outline-success');
            btnValidar.classList.add('btn-success');
        } else {
            btnValidar.classList.remove('btn-success', 'btn-secondary');
            btnValidar.classList.add('btn-primary');
        }
    }

    // Detectar turnos
    const setTurnos = new Set();
    [window.inscritos, window.reincorporados, window.aprovechamientos].forEach(fuente => {
        if (!fuente) return;
        fuente.forEach(r => {
            const rProg = String(r.Nombre_Programa || r.nombre_programa || '').trim().toUpperCase();
            const rMod  = String(r.Modalidad || r.modalidad || '').trim().toUpperCase();
            const rSem  = normalizarSemestre(r.Semestre || r.semestre);
            if (rProg === prog && rMod === mod && rSem === sem) {
                const t = r.Turno || r.turno;
                if (t && t !== 'NULL') setTurnos.add(String(t).trim());
            }
        });
    });

    let turnos = Array.from(setTurnos);
    const orden = { 'MATUTINO': 1, 'VESPERTINO': 2, 'MIXTO': 3, 'COMPLETO': 4 };
    turnos.sort((a, b) => (orden[a.toUpperCase()] || 99) - (orden[b.toUpperCase()] || 99));
    if (turnos.length === 0) turnos = ['Matutino'];
    window.turnosActualesPantalla = turnos;

    renderizarEncabezadoTabla(turnos);

    function mapearDatos(fuente) {
        const mapa = {};
        if (!fuente) return mapa;
        fuente.forEach(r => {
            const rProg = String(r.Nombre_Programa || r.nombre_programa || '').trim().toUpperCase();
            const rMod  = String(r.Modalidad || r.modalidad || '').trim().toUpperCase();
            const rSem  = normalizarSemestre(r.Semestre || r.semestre);
            if (rProg !== prog || rMod !== mod || rSem !== sem) return;
            const t   = String(r.Turno || r.turno || 'Sin Turno').trim();
            const s   = String(r.Sexo  || r.sexo  || '').toUpperCase().trim();
            const val = parseInt(r.Alumnos || r.alumnos || r.Matricula || r.matricula || 0);
            if (!mapa[t]) mapa[t] = { H: 0, M: 0 };
            if (s.startsWith('H') || s === '1') mapa[t].H += val;
            else if (s.startsWith('M') || s === '2') mapa[t].M += val;
        });
        return mapa;
    }

    // === CÓDIGO CORREGIDO ===
const datosInscritos = mapearDatos(window.inscritos);

// 1. Mapeamos desde window.reincorporados si existe
const datosReincorporados = mapearDatos(window.reincorporados);

// 2. Si no viene en window.reincorporados, buscamos si se guardó dentro de window.aprovechamientos
(window.aprovechamientos || []).forEach(r => {
    const rProg = String(r.Nombre_Programa || r.nombre_programa || '').trim().toUpperCase();
    const rMod  = String(r.Modalidad || r.modalidad || '').trim().toUpperCase();
    const rSem  = normalizarSemestre(r.Semestre || r.semestre);
    const sit   = String(r.Aprovechamiento || r.aprovechamiento || r.Situacion || r.situacion || '').trim().toLowerCase();

    if (rProg === prog && rMod === mod && rSem === sem && sit === 'reincorporados') {
        const t   = String(r.Turno || r.turno || 'Sin Turno').trim();
        const s   = String(r.Sexo  || r.sexo  || '').toUpperCase().trim();
        const val = parseInt(r.Alumnos || r.alumnos || 0);

        if (!datosReincorporados[t]) datosReincorporados[t] = { H: 0, M: 0 };
        if (s.startsWith('H') || s === '1') datosReincorporados[t].H = val;
        else if (s.startsWith('M') || s === '2') datosReincorporados[t].M = val;
    }
});










    const datosAprovechamiento = {};
    (window.aprovechamientos || []).forEach(r => {
        const rProg = String(r.Nombre_Programa || r.nombre_programa || '').trim().toUpperCase();
        const rMod  = String(r.Modalidad || r.modalidad || '').trim().toUpperCase();
        const rSem  = normalizarSemestre(r.Semestre || r.semestre);
        if (rProg !== prog || rMod !== mod || rSem !== sem) return;
        const sit = r.Aprovechamiento || r.aprovechamiento || r.Situacion || r.situacion || 'Sin especificar';
        const t   = String(r.Turno || r.turno || 'Sin Turno').trim();
        const s   = String(r.Sexo  || r.sexo  || '').toUpperCase().trim();
        const val = parseInt(r.Alumnos || r.alumnos || 0);
        if (!datosAprovechamiento[sit]) datosAprovechamiento[sit] = {};
        if (!datosAprovechamiento[sit][t]) datosAprovechamiento[sit][t] = { H: 0, M: 0 };
        if (s.startsWith('H')) datosAprovechamiento[sit][t].H += val;
        else if (s.startsWith('M')) datosAprovechamiento[sit][t].M += val;
    });

    crearFilaInput(tbody, 'Inscritos',      turnos, datosInscritos,      true,  'fila-matricula',      esSemestreBloqueado);
    crearFilaInput(tbody, 'Reincorporados', turnos, datosReincorporados, false, 'fila-matricula',      esSemestreBloqueado);
    crearFilaTotalizador(tbody, 'Total Matricula', turnos, 'total-matricula', '#e8f5e9');

    const trSep = document.createElement('tr');
    trSep.innerHTML = `<td colspan="${1 + turnos.length}" style="background:#dee2e6; height:6px; padding:0;"></td>`;
    tbody.appendChild(trSep);

    // === CÓDIGO CORREGIDO ===
    const exclusionSit = ['desertor', 'deserción', 'desercion', 'reincorporado', 'reincorporados'];

    const listaSit = Object.keys(datosAprovechamiento).length > 0
        ? Object.keys(datosAprovechamiento).filter(sit => !exclusionSit.includes(sit.toLowerCase().trim()))
        : ['Aprobado', 'Reprobado'];
    
    listaSit.forEach(sit => {
        crearFilaInput(tbody, sit, turnos, datosAprovechamiento[sit] || {}, false, 'fila-aprovechamiento', esSemestreBloqueado);
    });

    crearFilaDesercionCalculada(tbody, 'Deserción', turnos, '#f1f3f4');

    crearFilaTotalizador(tbody, 'Total Aprovechamiento', turnos, 'total-aprovechamiento', '#fff3e0');
    
    calcularTablaUnificada()

    if (scrollPendiente !== null) {
        setTimeout(() => { window.scrollTo({ top: scrollPendiente, behavior: 'auto' }); scrollPendiente = null; }, 100);
    }

    setTimeout(() => {
        aplicarBloqueoPorSemaforo();
        actualizarColoresPestanas();
        renderizarSeccionTotales();
    }, 80);
};

// ==========================================
// 9. Filas de inputs y totalizadores
// ==========================================

function crearFilaDesercionCalculada(tbody, titulo, turnos, colorFondo) {
    const tr = document.createElement('tr');
    tr.style.backgroundColor = colorFondo; 
    tr.style.borderBottom = '1px solid #dee2e6';
    
    // Celda de título
    tr.innerHTML = `<td style="font-weight:700; text-align:center; padding:14px 12px; border:1px solid #dee2e6; vertical-align:middle; font-size:14px; color:#555; background:#e9ecef; white-space:normal; word-break:keep-all; min-width:160px; width:160px; max-width:160px;">${titulo}</td>`;

    turnos.forEach((t, indexTurno) => {
        const borderRight = indexTurno < turnos.length - 1 ? 'border-right:3px solid #8B0A4A;' : '';
        
        tr.innerHTML += `
        <td style="padding:10px 8px; text-align:center; border:1px solid #dee2e6; ${borderRight}">
            <div style="display:inline-flex; gap:8px; justify-content:center; align-items:center;">
                
                <div style="display:inline-flex; align-items:center; gap:6px; padding:6px 14px; background:#e3f2fd; border-radius:8px; border:2px solid #90caf9;">
                    <span style="font-size:12px; color:#1976d2; font-weight:800; margin-right:4px;">H</span>
                    <span id="desercion-${t}-Hombre" class="span-desercion-calculada" data-turno="${t}" data-sexo="Hombre" style="font-weight:800; color:#546e7a; font-size:14px; display:inline-block; text-align:center;">0</span>
                </div>
                
                <div style="display:inline-flex; align-items:center; gap:6px; padding:6px 14px; background:#fce4ec; border-radius:8px; border:2px solid #f48fb1;">
                    <span style="font-size:12px; color:#c2185b; font-weight:800; margin-right:4px;">M</span>
                    <span id="desercion-${t}-Mujer" class="span-desercion-calculada" data-turno="${t}" data-sexo="Mujer" style="font-weight:800; color:#546e7a; font-size:14px; display:inline-block; text-align:center;">0</span>
                </div>
                
            </div>
        </td>`;
    });

    tbody.appendChild(tr);
}

function crearFilaInput(tbody, titulo, turnos, datosMapa, esSoloLectura, claseFila, esBloqueadoGral) {
    const tr = document.createElement('tr');
    tr.className = claseFila;
    tr.style.borderBottom = '1px solid #e0e0e0';
    tr.style.transition   = 'all 0.2s ease';
    tr.onmouseover = () => tr.style.backgroundColor = '#f5f5f5';
    tr.onmouseout  = () => tr.style.backgroundColor = '';

    let html = `<td style="font-weight:600; text-align:center; padding:14px 12px; border:1px solid #dee2e6; vertical-align:middle; font-size:14px; color:#333; background:#f8f9fa; white-space:normal; word-break:keep-all; min-width:160px; width:160px; max-width:160px;">${titulo}</td>`;

    turnos.forEach((t, indexTurno) => {
        const valoresDB = datosMapa[t] || { H: 0, M: 0 };
        const keyH = `${semestreActual}|${titulo}|${t}|Hombre`;
        const keyM = `${semestreActual}|${titulo}|${t}|Mujer`;

        let valH = cambiosGlobales.hasOwnProperty(keyH) ? cambiosGlobales[keyH] : (valoresDB.H !== 0 || esSoloLectura ? valoresDB.H : '');
        let valM = cambiosGlobales.hasOwnProperty(keyM) ? cambiosGlobales[keyM] : (valoresDB.M !== 0 || esSoloLectura ? valoresDB.M : '');

        let attr = ''; let bgH = '#fff'; let bgM = '#fff';
        if (esBloqueadoGral)    { attr = 'disabled'; bgH = '#e9ecef'; bgM = '#e9ecef'; }
        else if (esSoloLectura) { attr = 'readonly'; bgH = '#f8f9fa'; bgM = '#f8f9fa'; }

        const borderRight = indexTurno < turnos.length - 1 ? 'border-right:3px solid #8B0A4A;' : '';

        html += `
        <td style="padding:10px 8px; text-align:center; border:1px solid #dee2e6; ${borderRight}">
            <div style="display:inline-flex; gap:8px; justify-content:center; align-items:center;">
                <div style="display:inline-flex; align-items:center; gap:4px; padding:4px 8px; background:#e3f2fd; border-radius:6px; border:1px solid #90caf9;">
                    <div style="font-weight:700; color:#1976d2; font-size:12px; min-width:14px; text-align:center;">H</div>
                    <input type="number" min="0" max="9999" maxlength="4"
                        class="input-matricula-nueva"
                        data-tipo="${titulo}" data-turno="${t}" data-sexo="Hombre"
                        onkeydown="if(['-','.','+','e','E',','].includes(event.key)) event.preventDefault();"
                        value="${valH}" oninput="registrarCambio(this)" ${attr}>
                </div>
                <div style="display:inline-flex; align-items:center; gap:4px; padding:4px 8px; background:#fce4ec; border-radius:6px; border:1px solid #f48fb1;">
                    <div style="font-weight:700; color:#c2185b; font-size:12px; min-width:14px; text-align:center;">M</div>
                    <input type="number" min="0" max="9999" maxlength="4"
                        class="input-matricula-nueva"
                        data-tipo="${titulo}" data-turno="${t}" data-sexo="Mujer"
                        onkeydown="if(['-','.','+','e','E',','].includes(event.key)) event.preventDefault();"
                        value="${valM}" oninput="registrarCambio(this)" ${attr}>
                </div>
            </div>
        </td>`;
    });

    tr.innerHTML = html;
    tbody.appendChild(tr);
}
function crearFilaTotalizador(tbody, titulo, turnos, idBase, colorFondo) {
    const tr = document.createElement('tr');
    tr.style.backgroundColor = colorFondo;
    tr.style.borderTop       = '2px solid #dee2e6';
    // --- NUEVAS LÍNEAS PARA FIJAR LA FILA ---
    tr.style.position  = 'sticky';
    tr.style.bottom    = '0';     // Lo pega al borde inferior del contenedor
    tr.style.zIndex    = '10';    // Asegura que no sea tapado por otras filas al hacer scroll
    tr.style.boxShadow = '0px -3px 5px rgba(0, 0, 0, 0.05)'; 
    // ----------------------------------------

    let html = `<td style="text-align:right; padding:14px 12px; font-weight:700; font-size:14px; border:1px solid #dee2e6; color:#333; background:#f8f9fa; white-space:normal; word-break:keep-all; min-width:160px; width:160px; max-width:160px;">${titulo}:</td>`;

    turnos.forEach((t, indexTurno) => {
        const borderRight = indexTurno < turnos.length - 1 ? 'border-right:3px solid #8B0A4A;' : '';
        html += `
        <td style="text-align:center; border:1px solid #dee2e6; ${borderRight} padding:12px 8px;">
            <div style="display:inline-flex; gap:10px; justify-content:center; align-items:center;">
                <div style="display:inline-flex; align-items:center; gap:6px; padding:6px 14px; background:#e3f2fd; border-radius:8px; border:2px solid #90caf9;">
                    <span style="font-size:12px; color:#1976d2; font-weight:800;">H</span>
                    <span id="${idBase}-${t}-Hombre" style="font-weight:800; color:#1976d2; font-size:18px; min-width:18px; display:inline-block; text-align:center; line-height:1;">0</span>
                </div>
                <div style="display:inline-flex; align-items:center; gap:6px; padding:6px 14px; background:#fce4ec; border-radius:8px; border:2px solid #f48fb1;">
                    <span style="font-size:12px; color:#c2185b; font-weight:800;">M</span>
                    <span id="${idBase}-${t}-Mujer" style="font-weight:800; color:#c2185b; font-size:18px; min-width:18x; display:inline-block; text-align:center; line-height:1;">0</span>
                </div>
            </div>
        </td>`;
    });

    tr.innerHTML = html;
    tbody.appendChild(tr);
}
// ==========================================
// 10. Cálculos
// ==========================================
window.registrarCambio = function (input) {
    input.value = input.value.replace(/[^0-9]/g, '').slice(0, 4);
    const key = `${semestreActual}|${input.dataset.tipo}|${input.dataset.turno}|${input.dataset.sexo}`;
    cambiosGlobales[key] = input.value === '' ? '' : parseInt(input.value);
    calcularTablaUnificada();

    // Sincronizar deserción calculada del semestre actual en cambiosGlobales
    document.querySelectorAll('#tabla-body .span-desercion-calculada').forEach(span => {
        const valD = parseInt(span.dataset.valor ?? span.textContent.replace(/,/g, ''), 10) || 0;
        const keyD = `${semestreActual}|Deserción|${span.dataset.turno}|${span.dataset.sexo}`;
        cambiosGlobales[keyD] = valD;
    });

    renderizarSeccionTotales();
};

window.calcularTablaUnificada = function () {
    // 1. Calcular e inyectar Totales de Matrícula
    const sumaMatricula = {};
    document.querySelectorAll('.fila-matricula input').forEach(input => {
        const key = `${input.dataset.turno}-${input.dataset.sexo}`;
        sumaMatricula[key] = (sumaMatricula[key] || 0) + (parseInt(input.value) || 0);
    });
    Object.entries(sumaMatricula).forEach(([key, val]) => {
        const span = document.getElementById(`total-matricula-${key}`);
        if (span) span.textContent = Number(val || 0).toLocaleString('en-US');
    });

    // 2. Calcular la suma de los campos de Aprovechamiento EDITABLES (Aprobados, Reprobados...)
    const sumaAprovEditables = {};
    document.querySelectorAll('.fila-aprovechamiento input').forEach(input => {
        const key = `${input.dataset.turno}-${input.dataset.sexo}`;
        sumaAprovEditables[key] = (sumaAprovEditables[key] || 0) + (parseInt(input.value) || 0);
    });

    // 3. NUEVO: Calcular Deserción Dinámica e Inyectar en los elementos especiales
    if (window.turnosActualesPantalla) {
        window.turnosActualesPantalla.forEach(t => {
            ['Hombre', 'Mujer'].forEach(s => {
                const key = `${t}-${s}`;
                const totalM = sumaMatricula[key] || 0;
                const totalAprovRestante = sumaAprovEditables[key] || 0;
                
                // Fórmula: Total Matricula - Suma del resto
                const desercionCalculada = Math.max(0, totalM - totalAprovRestante); 
                
                // Inyectamos el valor en la fila gris
                const spanDesercion = document.getElementById(`desercion-${t}-${s}`);
                if (spanDesercion) {
                    spanDesercion.textContent = Number(desercionCalculada || 0).toLocaleString('en-US');
                    spanDesercion.dataset.valor = desercionCalculada;
                }

                // 4. Actualizar el Totalizador Final (Aprovechamiento Completo = Editables + Deserción)
                const spanTotalAprov = document.getElementById(`total-aprovechamiento-${key}`);
                if (!spanTotalAprov) return;

                const totalAprovechamientoCompleto = totalAprovRestante + desercionCalculada;

                if (totalM !== totalAprovechamientoCompleto) {
                    spanTotalAprov.style.color = '#dc3545';
                    spanTotalAprov.innerHTML = `${Number(totalAprovechamientoCompleto || 0).toLocaleString('en-US')} <i class="fas fa-exclamation-circle" style="font-size:16px;"></i>`;
                } else {
                    spanTotalAprov.style.color = '#198754';
                    spanTotalAprov.innerHTML = `${Number(totalAprovechamientoCompleto || 0).toLocaleString('en-US')} <i class="fas fa-check" style="font-size:16px;"></i>`;
                }
            });
        });
    }
};

function hayErroresDeTotales() {
    calcularTablaUnificada();
    return document.body.innerHTML.includes('fa-exclamation-circle');
}

// ==========================================
// 11. Totales y Resumen (versión completa)
// ==========================================
// ==========================================
// Totales y Resumen (con Deserción Incluida)
// ==========================================
function obtenerTotalesAprovechamiento() {
    let totalH = 0, totalM = 0;
    const porConcepto = {};

    // 1. Obtener valores de los inputs editables (Aprobados, Reprobados, etc.)
    document.querySelectorAll('.fila-aprovechamiento input').forEach(input => {
        const val      = parseInt(input.value) || 0;
        const concepto = input.dataset.tipo || 'Sin especificar';
        const sexo     = input.dataset.sexo;

        if (!porConcepto[concepto]) porConcepto[concepto] = { H: 0, M: 0 };
        if (sexo === 'Hombre') { totalH += val; porConcepto[concepto].H += val; }
        else if (sexo === 'Mujer') { totalM += val; porConcepto[concepto].M += val; }
    });

    // 2. Sumar la Deserción Calculada desde las etiquetas en pantalla
    const spansDesercion = document.querySelectorAll('.span-desercion-calculada');
    if (spansDesercion.length > 0) {
        if (!porConcepto['Deserción']) porConcepto['Deserción'] = { H: 0, M: 0 };

        spansDesercion.forEach(span => {
            const val  = parseInt(span.dataset.valor ?? span.textContent.replace(/,/g, ''), 10) || 0;
            const sexo = span.dataset.sexo;

            if (sexo === 'Hombre') { totalH += val; porConcepto['Deserción'].H += val; }
            else if (sexo === 'Mujer') { totalM += val; porConcepto['Deserción'].M += val; }
        });
    }

    return { totalH, totalM, porConcepto };
}

function renderizarSeccionTotales() {
    let contenedor = document.getElementById('seccion-totales-aprovechamiento');

    if (!contenedor) {
        const actionsSection = document.querySelector('.actions-after-table') || document.querySelector('.actions-section');
        if (!actionsSection) return;
        contenedor = document.createElement('div');
        contenedor.id = 'seccion-totales-aprovechamiento';
        contenedor.style.cssText = 'margin:24px 0 0 0; padding:0 25px 32px 25px;';
        actionsSection.insertAdjacentElement('afterend', contenedor);
    }

    const { totalH, totalM, porConcepto } = obtenerTotalesAprovechamiento();
    const totalGeneral = totalH + totalM;
    const conceptos    = Object.keys(porConcepto);

    const filasHTML = conceptos.length > 0
        ? conceptos.map((concepto, i) => {
            const { H, M } = porConcepto[concepto];
            const total    = H + M;
            
            // Destacar visualmente si la fila es "Deserción"
            const esDesercion = concepto.toLowerCase() === 'deserción' || concepto.toLowerCase() === 'desercion';
            const bg          = esDesercion ? '#fef2f2' : (i % 2 === 0 ? '#ffffff' : '#fafafa');
            const colorTexto  = esDesercion ? '#991b1b' : '#333333';

            return `
            <tr style="background:${bg};">
                <td style="padding:12px 20px; border:1px solid #e0e0e0; font-size:14px; color:${colorTexto}; font-weight:${esDesercion ? '700' : '500'};">
                    ${concepto} ${esDesercion ? '<span style="font-size:11px; font-weight:normal; color:#dc2626;">(Calculada)</span>' : ''}
                </td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#1565c0; font-weight:700;">${Number(H || 0).toLocaleString('en-US')}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#ad1457; font-weight:700;">${Number(M || 0).toLocaleString('en-US')}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#750946; font-weight:800;">${Number(total || 0).toLocaleString('en-US')}</td>
            </tr>`;
        }).join('')
        : `<tr><td colspan="4" style="padding:24px; text-align:center; color:#999; font-style:italic; font-size:14px;">Sin datos capturados aún</td></tr>`;

    contenedor.innerHTML = `
        <div style="background:white; border-radius:14px; box-shadow:0 4px 20px rgba(0,0,0,.08); overflow:hidden;">
            <div style="background:linear-gradient(135deg,#750946,#8B0A4A); text-align:center; color:white; padding:16px 24px; font-size:17px; font-weight:700; letter-spacing:.3px;">📊 Resumen de Aprovechamiento — Semestre ${semestreActual}</div>
            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:collapse;">
                    <thead>
                        <tr>
                            <th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">Situación Académica</th>
                            <th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:#1565c0; color:white; border:1px solid rgba(255,255,255,.2);">Hombres</th>
                            <th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:#ad1457; color:white; border:1px solid rgba(255,255,255,.2);">Mujeres</th>
                            <th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">Total</th>
                        </tr>
                    </thead>
                    <tbody>${filasHTML}</tbody>
                    <tfoot>
                        <tr>
                            <td style="padding:14px 20px; text-align:center; font-weight:800; font-size:15px; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">TOTAL</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px; background:rgba(21,101,192,.85); color:white; border:1px solid rgba(255,255,255,.2);">${Number(totalH || 0).toLocaleString('en-US')}</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px; background:rgba(173,20,87,.85); color:white; border:1px solid rgba(255,255,255,.2);">${Number(totalM || 0).toLocaleString('en-US')}</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">${Number(totalGeneral || 0).toLocaleString('en-US')}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    `;
}

// Estado global de la unidad (para el botón de validación masiva)
function obtenerEstadoGlobalUnidad() {
    if (!window.aprovechamientos || window.aprovechamientos.length === 0)
        return { listoParaValidar: false, conteos: { 1:0, 2:0, 3:0 }, total: 0 };

    const mapaGlobal = {};
    window.aprovechamientos.forEach(r => {
        const prog  = String(r.Nombre_Programa || '').trim().toUpperCase();
        const mod   = String(r.Modalidad || '').trim().toUpperCase();
        const sem   = normalizarSemestre(r.Semestre || r.semestre);
        const idSem = r.Id_Semaforo ?? r.id_semaforo ?? 1;
        if (!prog || !mod || isNaN(sem) || sem <= 0) return;
        const key = `${prog}||${mod}||${sem}`;
        const actual = mapaGlobal[key] ?? 0;
        if (idSem > actual) mapaGlobal[key] = idSem;
    });

    const valores = Object.values(mapaGlobal);
    if (valores.length === 0) return { listoParaValidar: false, conteos: {1:0,2:0,3:0}, total: 0 };

    const conteos = { 1: 0, 2: 0, 3: 0 };
    valores.forEach(v => conteos[v] = (conteos[v] || 0) + 1);

    const listoParaValidar = conteos[1] === 0 && conteos[2] > 0;
    return { listoParaValidar, conteos, total: valores.length };
}

// Validar toda la unidad (función que llama al backend)
window.validarTodaLaUnidad = async function () {
    const periodoVal = document.getElementById('periodo-texto')?.textContent.trim() || '';
    const unidadVal  = document.getElementById('unidad-texto')?.textContent.trim()
                    || document.getElementById('unidad_academica')?.value?.trim() || '';

    let nivelVal = 'Superior';
    const fuentesNivel = [window.aprovechamientos, window.inscritos, window.reincorporados];
    for (const fuente of fuentesNivel) {
        if (fuente?.length) {
            const r = fuente.find(rec => rec.Nivel || rec.nivel);
            if (r) { nivelVal = r.Nivel || r.nivel || 'Superior'; break; }
        }
    }

    const { conteos, total } = obtenerEstadoGlobalUnidad();

    const confirmResult = await Swal.fire({
        title: '✅ ¿Validar toda la Unidad?',
        html: `
            <p style="margin-bottom:12px;">Estás a punto de <b>validar todos los programas y semestres</b> de la unidad académica:</p>
            <div style="background:#f8f9fa; border-radius:8px; padding:14px; margin-bottom:14px; text-align:left;">
                <div style="margin-bottom:6px;"><b>Unidad:</b> ${unidadVal}</div>
                <div style="margin-bottom:6px;"><b>Periodo:</b> ${periodoVal}</div>
                <div style="margin-bottom:6px;"><b>Nivel:</b> ${nivelVal}</div>
            </div>
            <div style="display:flex; gap:8px; justify-content:center; flex-wrap:wrap; margin-bottom:10px;">
                <span style="padding:4px 12px; border-radius:100px; background:rgba(239,159,39,.15); color:#854f0b; font-weight:600; font-size:13px;">
                    Pendientes: ${conteos[2]}
                </span>
                <span style="padding:4px 12px; border-radius:100px; background:rgba(99,153,34,.15); color:#3b6d11; font-weight:600; font-size:13px;">
                    Ya completos: ${conteos[3]}
                </span>
                <span style="padding:4px 12px; border-radius:100px; background:#e3f2fd; color:#1565c0; font-weight:600; font-size:13px;">
                    Total: ${total}
                </span>
            </div>
            <p style="color:#dc3545; font-size:13px; margin:0;">Esta acción <b>no se puede deshacer</b>. Todos los semestres quedarán bloqueados.</p>
        `,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#198754',
        cancelButtonColor: '#6c757d',
        confirmButtonText: '✅ Sí, Validar Todo',
        cancelButtonText: 'Cancelar',
        width: 520,
    });

    if (!confirmResult.isConfirmed) return;

    Swal.fire({
        title: 'Validando toda la unidad...',
        html: 'Procesando todos los programas y semestres...',
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading(),
    });

    try {
        const res = await fetch('/aprovechamiento/validar_unidad_completa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                periodo:          periodoVal,
                unidad_academica: unidadVal,
                nivel:            nivelVal,
            }),
        });

        const data = await res.json();

        if (!res.ok) {
            Swal.fire('Error', data.detail || 'No se pudo validar la unidad.', 'error');
            return;
        }

        await Swal.fire({
            title: '¡Unidad Validada!',
            text: 'Todos los programas y semestres han sido validados correctamente.',
            icon: 'success',
            timer: 2000,
            showConfirmButton: false,
        });

        guardarEstadoYRecargar();
    } catch (e) {
        Swal.fire('Error', 'Error de conexión al validar la unidad.', 'error');
    }
};

// Construir panel semáforo (resumen de programas)
function buildResumenSemaforo() {
    if (!window.aprovechamientos || window.aprovechamientos.length === 0) return '';

    const cfg = {
        1: { bar:'#e24b4a', bg:'rgba(226,75,74,.07)',  dot:'#e24b4a', label:'Sin datos', textColor:'#a32d2d' },
        2: { bar:'#ef9f27', bg:'rgba(239,159,39,.08)', dot:'#ef9f27', label:'Parcial',   textColor:'#854f0b' },
        3: { bar:'#639922', bg:'rgba(99,153,34,.07)',  dot:'#639922', label:'Completo',  textColor:'#3b6d11' },
    };

    const grupos = {};
    window.aprovechamientos.forEach(r => {
        const prog  = String(r.Nombre_Programa || '').trim();
        const mod   = String(r.Modalidad || '').trim();
        const sem   = normalizarSemestre(r.Semestre || r.semestre);
        const idSem = r.Id_Semaforo ?? r.id_semaforo ?? 1;
        if (!prog || !mod || isNaN(sem) || sem <= 0) return;
        const key = `${prog.toUpperCase()}||${mod.toUpperCase()}`;
        if (!grupos[key]) grupos[key] = { prog, mod, sems: {} };
        const actual = grupos[key].sems[sem] ?? 0;
        if (idSem > actual) grupos[key].sems[sem] = idSem;
    });

    const progActual = document.getElementById('programa')?.value?.trim().toUpperCase() || '';
    const modActual  = document.getElementById('modalidad')?.value?.trim().toUpperCase() || '';

    const totales = { 1:0, 2:0, 3:0 };
    Object.values(grupos).forEach(g =>
        Object.values(g.sems).forEach(id => totales[id] = (totales[id]||0)+1)
    );

    const gruposOrdenados = Object.entries(grupos)
        .sort(([, a], [, b]) => a.prog.localeCompare(b.prog, 'es'));

    const bloques = gruposOrdenados.map(([key, g]) => {
        const esActivo = key === `${progActual}||${modActual}`;
        const semestresList = Object.keys(g.sems).map(Number).sort((a,b)=>a-b);

        const tarjetas = semestresList.map(sem => {
            const id = g.sems[sem] ?? 1;
            const c  = cfg[id] || cfg[1];
            return `
            <div onclick="irASemestreGlobal('${g.prog.replace(/'/g,"\\'")}','${g.mod.replace(/'/g,"\\'")}',${sem})"
                 title="${g.prog} · ${g.mod} · Semestre ${sem} — ${c.label}"
                 style="position:relative;cursor:pointer;border-radius:6px;
                        border:1px solid rgba(0,0,0,.08);background:${c.bg};
                        padding:6px 8px 5px;transition:transform .12s,box-shadow .12s;
                        overflow:hidden;min-width:0;"
                 onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 10px rgba(0,0,0,.12)'"
                 onmouseout="this.style.transform='';this.style.boxShadow=''">
                <div style="position:absolute;top:0;left:0;right:0;height:3px;background:${c.bar};border-radius:6px 6px 0 0;"></div>
                <div style="font-size:10px;color:#999;font-weight:500;margin-bottom:2px;">Sem. ${sem}</div>
                <div style="display:flex;align-items:center;gap:4px;">
                    <span style="width:7px;height:7px;border-radius:50%;background:${c.dot};flex-shrink:0;display:inline-block;"></span>
                    <span style="font-size:10px;font-weight:600;color:${c.textColor};white-space:nowrap;">${c.label}</span>
                </div>
            </div>`;
        }).join('');

        const bordeActivo = esActivo
            ? 'border:2px solid #750946; box-shadow:0 0 0 3px rgba(110,3,67,.1);'
            : 'border:1px solid #e8e8e8;';

        const badgeActivo = esActivo
            ? `<span style="font-size:10px;padding:2px 8px;border-radius:100px;background:#750946;color:white;font-weight:600;flex-shrink:0;">Activo</span>`
            : '';

        const shortProg = g.prog.length > 45 ? g.prog.slice(0,43)+'…' : g.prog;

        return `
        <div style="background:white;border-radius:10px;${bordeActivo} padding:12px 14px;">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:10px;">
                <div style="min-width:0;">
                    <div style="font-size:12px;font-weight:600;color:#333;line-height:1.3;margin-bottom:2px;" title="${g.prog}">${shortProg}</div>
                    <div style="font-size:11px;color:#888;">${g.mod}</div>
                </div>
                ${badgeActivo}
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(72px,1fr));gap:6px;">
                ${tarjetas}
            </div>
        </div>`;
    }).join('');

    const estadoGlobal = obtenerEstadoGlobalUnidad();
    

    if (estadoGlobal.listoParaValidar && !document.getElementById('style-pulse-green')) {
        const styleEl = document.createElement('style');
        styleEl.id = 'style-pulse-green';
        styleEl.textContent = `
            @keyframes pulseGreen {
                0%,100% { box-shadow:0 3px 10px rgba(27,138,62,.4); }
                50%      { box-shadow:0 3px 22px rgba(27,138,62,.75); }
            }`;
        document.head.appendChild(styleEl);
    }

    return `
    <div style="margin-top:28px;background:white;border-radius:14px;box-shadow:0 4px 20px rgba(0,0,0,.08);overflow:hidden;">
        <div style="background:linear-gradient(135deg,#750946,#8B0A4A);padding:14px 20px;
                    display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
            <span style="color:white;font-size:16px;font-weight:700;">📋 Estado de captura — todos los programas</span>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                <span style="font-size:11px;padding:3px 10px;border-radius:100px;background:rgba(226,75,74,.3);color:#ffcfcf;font-weight:600;">Sin datos: ${totales[1]}</span>
                <span style="font-size:11px;padding:3px 10px;border-radius:100px;background:rgba(239,159,39,.3);color:#ffe8b0;font-weight:600;">Parcial: ${totales[2]}</span>
                <span style="font-size:11px;padding:3px 10px;border-radius:100px;background:rgba(99,153,34,.3);color:#d0edaa;font-weight:600;">Completo: ${totales[3]}</span>
            </div>
        </div>
        <div style="padding:10px 20px;display:flex;gap:16px;flex-wrap:wrap;border-bottom:1px solid #f0f0f0;background:#fafafa;">
            <span style="font-size:11px;color:#888;display:flex;align-items:center;gap:4px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#e24b4a;display:inline-block;"></span>Sin datos
            </span>
            <span style="font-size:11px;color:#888;display:flex;align-items:center;gap:4px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#ef9f27;display:inline-block;"></span>Datos parciales
            </span>
            <span style="font-size:11px;color:#888;display:flex;align-items:center;gap:4px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#639922;display:inline-block;"></span>Datos completos
            </span>
            <span style="font-size:11px;color:#bbb;margin-left:auto;">Clic en un semestre para navegar</span>
        </div>
        <div style="padding:16px 20px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;">
            ${bloques}
        </div>
    </div>`;
}

function irASemestreGlobal(prog, mod, sem) {
    const programaSelect  = document.getElementById('programa');
    const modalidadSelect = document.getElementById('modalidad');
    if (!programaSelect || !modalidadSelect) return;

    const optProg = Array.from(programaSelect.options).find(o => o.value === prog);
    if (optProg) {
        programaSelect.value = prog;
        cambiosGlobales = {}; estadosSemaforoPorSemestre = {};
        const secTot = document.getElementById('seccion-totales-aprovechamiento');
        if (secTot) secTot.remove();

        modalidadSelect.innerHTML = '';
        const modSet = new Set();
        window.aprovechamientos.forEach(item => {
            if (item.Nombre_Programa === prog && item.Modalidad && !modSet.has(item.Modalidad)) {
                modSet.add(item.Modalidad);
                const opt = document.createElement('option');
                opt.value = item.Modalidad;
                opt.textContent = item.Modalidad;
                modalidadSelect.appendChild(opt);
            }
        });

        const optMod = Array.from(modalidadSelect.options).find(o => o.value === mod);
        if (optMod) modalidadSelect.value = mod;

        window.cargarSemestresTabs(prog, mod, sem);

        setTimeout(() => {
            const cont = document.querySelector('.tabla-matricula-container');
            if (cont) {
                const rect = cont.getBoundingClientRect();
                window.scrollTo({ top: window.pageYOffset + rect.top - 150, behavior: 'smooth' });
            }
        }, 300);
    }
}

function renderizarSeccionTotales() {
    let contenedor = document.getElementById('seccion-totales-aprovechamiento');

    if (!contenedor) {
        const actionsSection = document.querySelector('.actions-after-table') || document.querySelector('.actions-section');
        if (!actionsSection) return;
        contenedor = document.createElement('div');
        contenedor.id = 'seccion-totales-aprovechamiento';
        contenedor.style.cssText = 'margin:24px 0 0 0; padding:0 25px 32px 25px;';
        actionsSection.insertAdjacentElement('afterend', contenedor);
    }

    const { totalH, totalM, porConcepto } = obtenerTotalesAprovechamiento();
    const totalGeneral = totalH + totalM;
    const conceptos    = Object.keys(porConcepto);

    const filasHTML = conceptos.length > 0
        ? conceptos.map((concepto, i) => {
            const { H, M } = porConcepto[concepto];
            const total    = H + M;
            const bg       = i % 2 === 0 ? '#ffffff' : '#fafafa';
            return `
            <tr style="background:${bg};">
                <td style="padding:12px 20px; border:1px solid #e0e0e0; font-size:14px; color:#333; font-weight:500;">${concepto}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#1565c0; font-weight:700;">${H.toLocaleString()}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#ad1457; font-weight:700;">${M.toLocaleString()}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#750946; font-weight:800;">${total.toLocaleString()}</td>
            </tr>`;
        }).join('')
        : `<tr><td colspan="4" style="padding:24px; text-align:center; color:#999; font-style:italic; font-size:14px;">Sin datos capturados aún</td></tr>`;

    contenedor.innerHTML = `

        <div style="background:white; border-radius:14px; box-shadow:0 4px 20px rgba(0,0,0,.08); overflow:hidden;">
            <div style="background:linear-gradient(135deg,#750946,#8B0A4A); text-align:center;      color:white; padding:16px 24px; font-size:17px; font-weight:700; letter-spacing:.3px;">📊 Resumen de Aprovechamiento — Semestre ${semestreActual}</div>
            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:collapse;">
                    <thead>
                        <tr><th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">Situación Académica</th>
                            <th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:#1565c0; color:white; border:1px solid rgba(255,255,255,.2);">Hombres</th>
                            <th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:#ad1457; color:white; border:1px solid rgba(255,255,255,.2);">Mujeres</th>
                            <th style="padding:14px 20px; text-align:center; font-size:14px; font-weight:700; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">Total</th>
                        </tr>
                    </thead>
                    <tbody>${filasHTML}</tbody>
                    <tfoot>
                        <tr>
                            <td style="padding:14px 20px; text-align:center; font-weight:800; font-size:15px; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">TOTAL</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px; background:rgba(21,101,192,.85); color:white; border:1px solid rgba(255,255,255,.2);">${totalH.toLocaleString()}</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px; background:rgba(173,20,87,.85); color:white; border:1px solid rgba(255,255,255,.2);">${totalM.toLocaleString()}</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px; background:linear-gradient(135deg,#750946,#8B0A4A); color:white; border:1px solid rgba(255,255,255,.2);">${totalGeneral.toLocaleString()}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
        <!-- Agregar un simbolo de pesos {buildResumenSemaforo()} -->

    `;
}

// ==========================================
// 12. Bloqueo por Semáforo
// ==========================================
// ==========================================
// 12. Bloqueo por Semáforo
// ==========================================
function aplicarBloqueoPorSemaforo() {
    const estado      = estadosSemaforoPorSemestre[semestreActual] ?? 1;
    const bloqueado   = (estado === 3);
    const btnGuardar = document.getElementById('btn-guardar-matricula');
    const btnValidar = document.getElementById('btn-validar-matricula');
    const btnLimpiar = document.getElementById('btn-limpiar-formulario'); // ID de tu botón de limpiar

    if (bloqueado) {
        deshabilitarTodaLaVista();
        
        // Ocultar botón Guardar
        if (btnGuardar) { 
            btnGuardar.disabled = true;  
            btnGuardar.style.display = 'none'; 
        }
        
        // Cambiar botón Validar a Verde con el texto "Semestre Finalizado"
        if (btnValidar) { 
            btnValidar.disabled = true;  
            btnValidar.innerHTML = '✅ Semestre Finalizado'; 
            btnValidar.classList.remove('btn-primary', 'btn-secondary', 'btn-outline-success');
            btnValidar.classList.add('btn-success');
            btnValidar.style.display = 'inline-block';
        }

        // Ocultar botón Limpiar Formulario
        if (btnLimpiar) {
            btnLimpiar.style.display = 'none';
        }

    } else {
        // Restaurar estado activo/editable
        if (btnGuardar) { 
            btnGuardar.disabled = false; 
            btnGuardar.style.display = 'inline-block'; 
        }
        
        if (btnValidar) { 
            btnValidar.disabled = false; 
            btnValidar.innerHTML = '✅ Finalizar Captura'; 
            btnValidar.classList.remove('btn-success', 'btn-secondary');
            btnValidar.classList.add('btn-primary');
            btnValidar.style.display = 'inline-block';
        }

        // Mostrar botón Limpiar Formulario si el semestre no está bloqueado
        if (btnLimpiar) {
            btnLimpiar.style.display = 'inline-block';
        }
    }
}

function deshabilitarTodaLaVista() {
    document.querySelectorAll('input.input-matricula-nueva').forEach(input => {
        input.disabled = true;
        input.classList.add('input-disabled');
        Object.assign(input.style, { backgroundColor: '#e9ecef', cursor: 'not-allowed' });
    });
}

// ==========================================
// 13. Helpers de envío y memoria local
// ==========================================
function prepararDatosParaEnvio(claves) {
    const programaVal  = document.getElementById('programa')?.value.trim();
    const modalidadVal = document.getElementById('modalidad')?.value.trim();
    const periodoVal   = document.getElementById('periodo-texto')?.textContent.trim() || '';

    let rama = '', sigla = '', nivel = 'Superior';
    const fuentes = [window.aprovechamientos, window.inscritos, window.reincorporados];
    for (const fuente of fuentes) {
        if (fuente?.length) {
            const r = fuente.find(r =>
                String(r.Nombre_Programa || r.nombre_programa || '').trim().toUpperCase() === String(programaVal).toUpperCase()
            );
            if (r) { rama = r.Nombre_Rama || r.Rama || r.rama || ''; sigla = r.Sigla || r.sigla || ''; nivel = r.Nivel || r.nivel || 'Superior'; break; }
        }
    }
    if (!rama) { const el = document.getElementById('rama-texto'); if (el) rama = el.textContent.trim(); }

    const datos     = [];
    const procesadas = new Set();

    claves.forEach(key => {
        if (procesadas.has(key)) return;
        procesadas.add(key);
        const partes   = key.split('|');
        const semNum   = parseInt(partes[0]);
        const concepto = partes[1];
        if (concepto === 'Inscritos') return;
        let valor = cambiosGlobales[key];
        if (valor === '' || valor === null || valor === undefined) valor = 0;
        else valor = parseInt(valor);
        datos.push({
            periodo: periodoVal, programa: programaVal, modalidad: modalidadVal,
            semestre: semestreNumeroATexto(semNum), rama, Nombre_Rama: rama,
            sigla, nivel, id_semaforo: 2,
            situacion_academica: concepto, turno: partes[2], sexo: partes[3], alumnos: valor
        });
    });
    return datos;
}

function actualizarMemoriaLocalConCambios(datosGuardados) {
    if (!window.aprovechamientos) window.aprovechamientos = [];
    const progVal = document.getElementById('programa')?.value.trim().toUpperCase();
    const modVal  = document.getElementById('modalidad')?.value.trim().toUpperCase();

    datosGuardados.forEach(dato => {
        const semNum = normalizarSemestre(dato.semestre);
        const existente = window.aprovechamientos.find(r => {
            const rProg    = String(r.Nombre_Programa || '').trim().toUpperCase();
            const rMod     = String(r.Modalidad || '').trim().toUpperCase();
            const rSem     = normalizarSemestre(r.Semestre || r.semestre);
            const rSit     = r.Aprovechamiento || r.aprovechamiento || r.Situacion || r.situacion;
            const rTurno   = r.Turno || r.turno;
            const rSexo    = r.Sexo  || r.sexo;
            const rSitNorm = String(rSit || '').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
            const dSitNorm = String(dato.situacion_academica || '').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
            return rProg === progVal && rMod === modVal && rSem === semNum &&
                   rSitNorm === dSitNorm && rTurno === dato.turno &&
                   String(rSexo).charAt(0).toUpperCase() === String(dato.sexo).charAt(0).toUpperCase();
        });
        if (existente) {
            existente.Alumnos     = dato.alumnos;
            if (existente.alumnos !== undefined) existente.alumnos = dato.alumnos;
            existente.Id_Semaforo = dato.id_semaforo;
        } else {
            window.aprovechamientos.push({
                Nombre_Programa: progVal, Modalidad: modVal, Semestre: dato.semestre,
                Aprovechamiento: dato.situacion_academica, Situacion: dato.situacion_academica,
                Turno: dato.turno, Sexo: dato.sexo, Alumnos: dato.alumnos,
                Id_Semaforo: dato.id_semaforo, Nivel: dato.nivel,
                Rama: dato.rama, Sigla: dato.sigla, Nombre_Rama: dato.Nombre_Rama
            });
        }
    });
}

function guardarEstadoYRecargar() {
    const prog   = document.getElementById('programa')?.value.trim();
    const mod    = document.getElementById('modalidad')?.value.trim();
    const scroll = window.scrollY;
    localStorage.setItem('filtro_aprovechamiento', JSON.stringify({
        programa: prog, modalidad: mod, semestre: semestreActual, scrollPos: scroll
    }));
    window.location.reload();
}

// ==========================================
// 14. Guardar y Validar (Capturista)
// ==========================================
window.guardarTablaUnificada = async function () {
    if (hayErroresDeTotales()) {
        const r = await Swal.fire({ title: '⚠️ Totales no coinciden', text: '¿Deseas guardar de todos modos?', icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, guardar' });
        if (!r.isConfirmed) return;
    }

    // Si no había cambios previos en memoria, recopilar todos los inputs actuales del formulario
    const clavesPrevias = Object.keys(cambiosGlobales);
    if (clavesPrevias.length === 0) {
        document.querySelectorAll('#tabla-body input[type="number"]').forEach(input => {
            let v = input.value.trim();
            if (v === '' || isNaN(v)) { v = 0; } else v = parseInt(v);
            const key = `${semestreActual}|${input.dataset.tipo}|${input.dataset.turno}|${input.dataset.sexo}`;
            cambiosGlobales[key] = v;
        });
    }

    // Registrar siempre la deserción calculada del semestre actual
    document.querySelectorAll('#tabla-body .span-desercion-calculada').forEach(span => {
        const valD = parseInt(span.dataset.valor ?? span.textContent.replace(/,/g, ''), 10) || 0;
        const keyD = `${semestreActual}|Deserción|${span.dataset.turno}|${span.dataset.sexo}`;
        cambiosGlobales[keyD] = valD;
    });

    const claves = Object.keys(cambiosGlobales);
    if (claves.length === 0) { Swal.fire('Información', 'No hay cambios pendientes.', 'info'); return; }

    const datos = prepararDatosParaEnvio(claves);
    if (datos.length === 0) return;

    Swal.fire({ title: 'Guardando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

    try {
        const res = await fetch('/aprovechamiento/guardar_progreso_aprovechamiento', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos)
        });
        if (!res.ok) throw new Error(await res.text());

        const periodoVal = document.getElementById('periodo-texto')?.textContent.trim() || '';
        await fetch('/aprovechamiento/actualizar_aprovechamiento', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ periodo: periodoVal })
        });

        actualizarMemoriaLocalConCambios(datos);
        cambiosGlobales = {};
        await Swal.fire({ title: '¡Guardado!', text: 'Datos actualizados correctamente.', icon: 'success', timer: 1500, showConfirmButton: false });
        guardarEstadoYRecargar();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

window.validarCapturaSemestre = async function () {
   if (hayErroresDeTotales()) {
    await Swal.fire({
        icon: 'error',
        title: 'No se puede finalizar el semestre',
        text: 'Los totales de matrícula y aprovechamiento no coinciden. Corrija los datos antes de finalizar.',
        confirmButtonText: 'Entendido'
    });
    return;
}

    const programaVal   = document.getElementById('programa')?.value.trim();
    const modalidadVal  = document.getElementById('modalidad')?.value.trim();
    const semestreTexto = semestreNumeroATexto(semestreActual);

    if (!programaVal || !modalidadVal) { Swal.fire('Error', 'Selecciona Programa y Modalidad', 'error'); return; }

    const confirmResult = await Swal.fire({
        title: `¿Finalizar ${semestreTexto} Semestre?`,
        html: `Estás a punto de validar:<br><b>Programa:</b> ${programaVal}<br><b>Modalidad:</b> ${modalidadVal}<br>
               <b>Semestre:</b> <span style="color:#d33; font-weight:bold;">${semestreTexto}</span><br><br>
               El semáforo cambiará a <b>VERDE</b> y la edición se bloqueará.`,
        icon: 'question', showCancelButton: true, confirmButtonColor: '#198754', confirmButtonText: 'Sí, Finalizar'
    });
    if (!confirmResult.isConfirmed) return;

    Swal.fire({ title: 'Validando...', html: 'Recopilando toda la información...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

    const periodoVal = document.getElementById('periodo-texto')?.textContent.trim() || '';
    let rama = '', sigla = '', nivel = 'Superior';
    const fuentes = [window.aprovechamientos, window.inscritos, window.reincorporados];
    for (const fuente of fuentes) {
        if (fuente?.length) {
            const r = fuente.find(reg => String(reg.Nombre_Programa || reg.nombre_programa || '').trim().toUpperCase() === programaVal.toUpperCase());
            if (r) { rama = r.Nombre_Rama || r.Rama || r.rama || ''; sigla = r.Sigla || r.sigla || ''; nivel = r.Nivel || r.nivel || 'Superior'; break; }
        }
    }
    if (!rama) { const el = document.getElementById('rama-texto'); if (el) rama = el.textContent.trim(); }

    try {
        document.querySelectorAll('#tabla-body input[type="number"]').forEach(input => {
            let v = input.value.trim();
            if (v === '' || isNaN(v)) { v = 0; input.value = 0; } else v = parseInt(v);
            const key = `${semestreActual}|${input.dataset.tipo}|${input.dataset.turno}|${input.dataset.sexo}`;
            cambiosGlobales[key] = v;
        });

        // Registrar también la deserción calculada del semestre actual
        document.querySelectorAll('#tabla-body .span-desercion-calculada').forEach(span => {
            const v = parseInt(span.dataset.valor ?? span.textContent.replace(/,/g, ''), 10) || 0;
            const key = `${semestreActual}|Deserción|${span.dataset.turno}|${span.dataset.sexo}`;
            cambiosGlobales[key] = v;
        });

        const temporal = prepararDatosParaEnvio(Object.keys(cambiosGlobales));
        if (temporal.length > 0) {
            const resG = await fetch('/aprovechamiento/guardar_progreso_aprovechamiento', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(temporal)
            });
            if (!resG.ok) throw new Error('Error guardando los datos completos del semestre.');
            actualizarMemoriaLocalConCambios(temporal);
            cambiosGlobales = {};
        }

        const resValidar = await fetch('/aprovechamiento/finalizar_captura_semestre', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ programa: programaVal, modalidad: modalidadVal, semestre: semestreTexto, periodo: periodoVal, rama, Nombre_Rama: rama, sigla, nivel })
        });
        const jsonValidar = await resValidar.json();

        if (resValidar.ok) {
            estadosSemaforoPorSemestre[semestreActual] = 3;
            actualizarColoresPestanas();
            deshabilitarTodaLaVista();

            await Swal.fire({ title: '¡Finalizado!', text: 'Semestre validado correctamente.', icon: 'success', timer: 1500, showConfirmButton: false });

            const idx = semestresDisponiblesSP.indexOf(semestreActual);
            if (idx !== -1 && idx < semestresDisponiblesSP.length - 1) {
                setTimeout(() => seleccionarSemestre(semestresDisponiblesSP[idx + 1]), 1000);
            } else {
                guardarEstadoYRecargar();
            }
        } else {
            throw new Error(jsonValidar.detail || 'Error al finalizar');
        }
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

// ==========================================
// 16. Panel de Rechazo y Notificaciones
// ==========================================
window.abrirPanelRechazo = function () {
    const panel    = document.getElementById('panel-rechazo');
    const textarea = document.getElementById('motivo-rechazo-panel');
    const contador = document.getElementById('contador-caracteres-panel');
    if (!panel) return;

    if (panel.style.display === 'block') { cerrarPanelRechazo(); return; }

    if (textarea) textarea.value = '';
    if (contador) contador.textContent = '0';

    // === CAMBIO MÍNIMO: Fijar posición flotante y mostrar ===
    Object.assign(panel.style, { display: 'block', position: 'fixed', bottom: '20px', right: '20px', zIndex: '1050' });

    setTimeout(() => panel.classList.add('panel-abierto'), 10);
    setTimeout(() => { if (textarea) textarea.focus(); }, 300);
    // Se elimina el scrollIntoView ya que no es necesario scrollear
};

window.cerrarPanelRechazo = function () {
    const panel    = document.getElementById('panel-rechazo');
    const textarea = document.getElementById('motivo-rechazo-panel');
    const contador = document.getElementById('contador-caracteres-panel');
    if (!panel) return;
    panel.classList.remove('panel-abierto');
    if (textarea) textarea.value = '';
    if (contador) contador.textContent = '0';
    setTimeout(() => { panel.style.display = 'none'; }, 300);
};

window.actualizarContadorPanel = function () {
    const textarea = document.getElementById('motivo-rechazo-panel');
    const contador = document.getElementById('contador-caracteres-panel');
    if (!textarea || !contador) return;
    contador.textContent = textarea.value.length;
    if (textarea.value.length > 230) { contador.style.color = '#dc3545'; contador.style.fontWeight = 'bold'; }
    else { contador.style.color = '#636569'; contador.style.fontWeight = 'normal'; }
};

window.togglePanelNotificaciones = function () {
    const panel = document.getElementById('panel-notificaciones');
    if (!panel) return;
    const abierto = panel.style.display === 'block';
    panel.style.display = abierto ? 'none' : 'block';
    if (!abierto) {
        const badge = document.querySelector('.notificacion-badge');
        if (badge) badge.style.display = 'none';
    }
};

window.mostrarBannerRechazo = function () {
    const banner = document.getElementById('banner-rechazo');
    const panel  = document.getElementById('panel-notificaciones');
    if (banner) {
        banner.style.display = 'flex';
        banner.style.animation = 'slideDownBanner 0.5s ease-out';
        setTimeout(() => banner.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }
    if (panel) panel.style.display = 'none';
};
let pantallaCarga = null;

function mostrarPantallaCarga(mensaje = "Guardando cambios...") {
    Swal.fire({
            title: 'Cargando información...',
            html: 'Consultando datos de aprovechamiento.<br>Por favor espere.',
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => { Swal.showLoading(); }
    });
}

function ocultarPantallaCarga() {
    Swal.close();
}
// ==========================================
// Verificar Totales del Semestre (Con Deserción)
// ==========================================
function verificarTotalesSemestre() {
    let sumaMatriculaH = 0, sumaMatriculaM = 0;
    let sumaAprovH = 0, sumaAprovM = 0;
    
    // 1. Sumar Inputs Editables de Matrícula (Inscritos y Reincorporados)
    document.querySelectorAll('#tabla-body tr.fila-matricula input.input-matricula-nueva').forEach(input => {
        const val = parseInt(input.value, 10) || 0;
        const sexo = input.dataset.sexo;
        if (sexo === 'Hombre') sumaMatriculaH += val;
        else if (sexo === 'Mujer') sumaMatriculaM += val;
    });

    // 2. Sumar Inputs Editables de Aprovechamiento (Aprobados, Reprobados, etc.)
    document.querySelectorAll('#tabla-body tr.fila-aprovechamiento input.input-matricula-nueva').forEach(input => {
        const val = parseInt(input.value, 10) || 0;
        const sexo = input.dataset.sexo;
        if (sexo === 'Hombre') sumaAprovH += val;
        else if (sexo === 'Mujer') sumaAprovM += val;
    });

    // 3. NUEVO: Sumar los valores de Deserción Calculada (.span-desercion-calculada)
    document.querySelectorAll('#tabla-body .span-desercion-calculada').forEach(span => {
        const val = parseInt(span.dataset.valor ?? span.textContent.replace(/,/g, ''), 10) || 0;
        const sexo = span.dataset.sexo;
        if (sexo === 'Hombre') sumaAprovH += val;
        else if (sexo === 'Mujer') sumaAprovM += val;
    });
    
    // Log detallado para depuración en consola
    console.log(`📊 Totales Verificados — Matrícula: H=${sumaMatriculaH}, M=${sumaMatriculaM} | Aprovechamiento + Deserción: H=${sumaAprovH}, M=${sumaAprovM}`);
    
    const coincide = (sumaMatriculaH === sumaAprovH && sumaMatriculaM === sumaAprovM);
    return { 
        coincide, 
        matriculaH: sumaMatriculaH, 
        matriculaM: sumaMatriculaM, 
        aprovH: sumaAprovH, 
        aprovM: sumaAprovM 
    };
}
// ==========================================
// Modal de progreso circular mejorado
// ==========================================
let modalProgreso = null;

function abrirModalProgresoCircular(total) {
    if (modalProgreso) {
        modalProgreso.close();
        modalProgreso = null;
    }
    Swal.fire({
        title: 'Validación Masiva en Progreso',
        html: `
            <div style="position: relative; width: 160px; height: 160px; margin: 0 auto;">
                <svg viewBox="0 0 120 120" style="transform: rotate(-90deg); width: 100%; height: 100%;">
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#e0e0e0" stroke-width="8" />
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#28a745" stroke-width="8"
                            stroke-dasharray="339.292" stroke-dashoffset="339.292"
                            class="progress-ring__circle" />
                </svg>
                <div id="progreso-porcentaje-modal" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 28px; font-weight: bold; color: #28a745;">0%</div>
            </div>
            <div id="progreso-texto-modal" style="margin-top: 20px; font-size: 16px; font-weight: 600; color: #333; text-align: center;">Preparando...</div>
            <div id="progreso-detalle-modal" style="margin-top: 8px; font-size: 13px; color: #636569; text-align: center;">0 / 0</div>
        `,
        allowOutsideClick: false,
        showConfirmButton: false,
        didOpen: () => {
            modalProgreso = Swal.getPopup();
            const circle = modalProgreso.querySelector('.progress-ring__circle');
            if (circle) {
                const radius = 54;
                const circumference = radius * 2 * Math.PI;
                circle.style.strokeDasharray = `${circumference} ${circumference}`;
                circle.style.strokeDashoffset = circumference;
                window.progressCircumference = circumference;
            } else {
                window.progressCircumference = 339.292;
            }
        }
    });
}

function actualizarModalProgresoCircular(actual, total, texto, detalle) {
    if (!modalProgreso) return;
    const percent = Math.round((actual / total) * 100);
    const circle = modalProgreso.querySelector('.progress-ring__circle');
    if (circle && window.progressCircumference) {
        const offset = window.progressCircumference - (percent / 100) * window.progressCircumference;
        circle.style.strokeDashoffset = offset;
    }
    const porcentajeSpan = modalProgreso.querySelector('#progreso-porcentaje-modal');
    if (porcentajeSpan) porcentajeSpan.innerText = `${percent}%`;
    const textoDiv = modalProgreso.querySelector('#progreso-texto-modal');
    if (textoDiv) textoDiv.innerText = texto;
    const detalleDiv = modalProgreso.querySelector('#progreso-detalle-modal');
    if (detalleDiv) detalleDiv.innerText = detalle;
}

function cerrarModalProgresoCircular() {
    if (modalProgreso) {
        Swal.close();
        modalProgreso = null;
    }
}

window.validarTodosLosSemestres = async function () {
    if (validacionMasivaEnCurso) {
        Swal.fire({ icon: 'info', title: 'En proceso', text: 'Ya hay una validación masiva en curso.' });
        return;
    }

    const confirmacion = await Swal.fire({
        title: 'Validación masiva de Aprovechamiento',
        html: '<p><strong>Se validarán TODOS los semestres pendientes.</strong><br>Los campos vacíos se rellenarán automáticamente con <strong>ceros</strong> para completar la validación.</p>',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, continuar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#28a745',
        cancelButtonColor: '#dc3545'
    });

    if (!confirmacion.isConfirmed) return;

    const periodo = document.getElementById('periodo-texto')?.textContent.trim() || '';
    if (!periodo) {
        await Swal.fire({ icon: 'warning', title: 'Periodo faltante', text: 'No se pudo obtener el periodo.' });
        return;
    }

    // Obtener todos los programas y modalidades únicos
    const progSet = new Set();
    const progModMap = new Map();
    (window.aprovechamientos || []).forEach(item => {
        const prog = item.Nombre_Programa;
        const mod = item.Modalidad;
        if (prog && mod) {
            progSet.add(prog);
            if (!progModMap.has(prog)) progModMap.set(prog, new Set());
            progModMap.get(prog).add(mod);
        }
    });
    const todosLosProgramas = Array.from(progSet).map(p => ({ Nombre_Programa: p }));

    if (todosLosProgramas.length === 0) {
        await Swal.fire({ icon: 'warning', title: 'Sin programas', text: 'No hay programas disponibles.' });
        return;
    }

    const programaSelect = document.getElementById('programa');
    const modalidadSelect = document.getElementById('modalidad');
    const semestreInput = document.getElementById('semestre');
    const turnoInput = document.getElementById('turno');
    const btnValidarTodos = document.getElementById('btn-validar-todos-semestres');

    if (!programaSelect || !modalidadSelect || !semestreInput || !turnoInput || !btnValidarTodos) {
        await Swal.fire({ icon: 'error', title: 'Error de vista', text: 'Faltan controles del formulario.' });
        return;
    }

    const estadoOriginal = {
        programa: programaSelect.value,
        modalidad: modalidadSelect.value,
        semestre: semestreInput.value,
        turno: turnoInput.value,
        textoBoton: btnValidarTodos.textContent
    };

    // Estructuras
    const plan = [];          // semestres pendientes (estado != 3)
    const resumen = [];       // para estadísticas
    let totalSemestresPlan = 0;
    let semestresYaCompletos = 0;
    let semestresProcesados = 0;
    let semestresExitosos = 0;
    let semestresConError = 0;
    let turnosRellenados = 0;  // contador de campos que se llenaron con cero
    let semestresErrorTotales = 0;

    btnValidarTodos.disabled = true;
    validacionMasivaEnCurso = true;

    try {
        // 1. Construir plan (solo semestres con semáforo != 3)
        for (const progItem of todosLosProgramas) {
            const programaNombre = progItem.Nombre_Programa;
            const modalidades = Array.from(progModMap.get(programaNombre) || []);

            if (modalidades.length === 0) {
                resumen.push({
                    programaNombre,
                    modalidadNombre: 'Sin modalidad',
                    semestresTotal: 0,
                    semestresOk: 0,
                    semestresCompletos: 0,
                    turnosOk: 0,
                    observaciones: ['Sin modalidades configuradas']
                });
                continue;
            }

            for (const modalidadNombre of modalidades) {
                // Obtener semestres para esta combinación
                const semSet = new Set();
                (window.aprovechamientos || []).forEach(item => {
                    if (item.Nombre_Programa === programaNombre && item.Modalidad === modalidadNombre) {
                        const sem = normalizarSemestre(item.Semestre || item.semestre);
                        if (!isNaN(sem) && sem > 0) semSet.add(sem);
                    }
                });
                let semestres = Array.from(semSet).sort((a,b)=>a-b);
                
                // Obtener estados de semáforo
                procesarEstadosSemaforoAprovechamiento(programaNombre, modalidadNombre);
                const semestresPendientes = [];
                let completosCombo = 0;
                for (const sem of semestres) {
                    const estado = estadosSemaforoPorSemestre[sem] ?? 1;
                    if (estado === 3) {
                        completosCombo++;
                        semestresYaCompletos++;
                    } else {
                        semestresPendientes.push(sem);
                    }
                }
                plan.push({
                    programaNombre,
                    modalidadNombre,
                    semestres: semestresPendientes
                });
                resumen.push({
                    programaNombre,
                    modalidadNombre,
                    semestresTotal: semestres.length,
                    semestresOk: 0,
                    semestresCompletos: completosCombo,
                    turnosOk: 0,
                    observaciones: []
                });
                totalSemestresPlan += semestresPendientes.length;
            }
        }

        if (totalSemestresPlan === 0) {
            await Swal.fire({
                icon: 'info',
                title: 'Sin semestres pendientes',
                html: `Ya hay ${semestresYaCompletos} semestre(s) completamente validados.<br>No hay semestres por procesar.`
            });
            return;
        }

        abrirModalProgresoCircular(totalSemestresPlan);
        actualizarModalProgresoCircular(0, totalSemestresPlan, 'Iniciando validación masiva...', `0 de ${totalSemestresPlan} semestres`);

        // Funciones auxiliares
        async function guardarSemestreSilencioso(programa, modalidad, semestreNum) {
            const inputs = document.querySelectorAll(
                '#tabla-body input.input-matricula-nueva'
            );
            const cambiosTemp = {};

            inputs.forEach(input => {
                const val = parseInt(input.value) || 0;
                const key = `${semestreNum}|${input.dataset.tipo}|${input.dataset.turno}|${input.dataset.sexo}`;
                cambiosTemp[key] = val;
                cambiosGlobales[key] = val;
            });

            // Incluir también la deserción calculada
            document.querySelectorAll('#tabla-body .span-desercion-calculada').forEach(span => {
                const val = parseInt(span.dataset.valor ?? span.textContent.replace(/,/g, ''), 10) || 0;
                const key = `${semestreNum}|Deserción|${span.dataset.turno}|${span.dataset.sexo}`;
                cambiosTemp[key] = val;
                cambiosGlobales[key] = val;
            });

            const claves = Object.keys(cambiosTemp);
            if (claves.length === 0) return;

            const datos = prepararDatosParaEnvio(claves);
            if (datos.length === 0) return;

            const res = await fetch('/aprovechamiento/guardar_progreso_aprovechamiento', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });
            if (!res.ok) throw new Error('Error guardando progreso');
            actualizarMemoriaLocalConCambios(datos);
        }

        async function finalizarSemestreSilencioso(programa, modalidad, semestreNum) {
            const semestreTexto = semestreNumeroATexto(semestreNum);
            const periodoVal = document.getElementById('periodo-texto')?.textContent.trim() || '';
            let rama = '', sigla = '', nivel = 'Superior';
            const fuentes = [window.aprovechamientos, window.inscritos, window.reincorporados];
            for (const fuente of fuentes) {
                if (fuente?.length) {
                    const r = fuente.find(reg => String(reg.Nombre_Programa || reg.nombre_programa || '').trim().toUpperCase() === programa.toUpperCase());
                    if (r) { rama = r.Nombre_Rama || r.Rama || r.rama || ''; sigla = r.Sigla || r.sigla || ''; nivel = r.Nivel || r.nivel || 'Superior'; break; }
                }
            }
            const res = await fetch('/aprovechamiento/finalizar_captura_semestre', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    programa, modalidad, semestre: semestreTexto, periodo: periodoVal,
                    rama, Nombre_Rama: rama, sigla, nivel
                })
            });
            if (!res.ok) throw new Error(await res.text());
            estadosSemaforoPorSemestre[semestreNum] = 3; // actualizar localmente
        }

        // 2. Ejecutar plan (solo semestres pendientes)
        for (const item of plan) {
            const resumenItem = resumen.find(r => r.programaNombre === item.programaNombre && r.modalidadNombre === item.modalidadNombre);
            if (!item.semestres.length) continue;

            programaSelect.value = item.programaNombre;
            const changeEvent = new Event('change', { bubbles: true });
            programaSelect.dispatchEvent(changeEvent);
            await new Promise(r => setTimeout(r, 300));
            modalidadSelect.value = item.modalidadNombre;
            await new Promise(r => setTimeout(r, 300));

            for (const semestreId of item.semestres) {
                actualizarModalProgresoCircular(
                    semestresProcesados,
                    totalSemestresPlan,
                    `${item.programaNombre} / ${item.modalidadNombre}`,
                    `Procesando semestre ${semestreId} (${semestresProcesados + 1} de ${totalSemestresPlan})`
                );

                try {
                    semestreActual = semestreId; // ← asegurar variable global correcta

                    // 1. Cargar tabla y esperar render real
                    await new Promise((resolve) => {
                        window.cargarTablaAprovechamiento(
                            item.programaNombre,
                            item.modalidadNombre,
                            semestreId
                        );
                        // Esperar a que el DOM tenga los inputs renderizados
                        let intentos = 0;
                        const interval = setInterval(() => {
                            const inputs = document.querySelectorAll(
                                '#tabla-body input.input-matricula-nueva'
                            );
                            intentos++;
                            if (inputs.length > 0 || intentos > 30) {
                                clearInterval(interval);
                                resolve();
                            }
                        }, 100);
                    });

                    // 2. Verificar ANTES de tocar nada
                    const { coincide, matriculaH, matriculaM, aprovH, aprovM } =
                        verificarTotalesSemestre();

                    console.log(
                        `📊 Sem ${semestreId} — Matrícula H=${matriculaH} M=${matriculaM}` +
                        ` | Aprov H=${aprovH} M=${aprovM} → Coinciden: ${coincide}`
                    );

                    if (!coincide) {
                        const errorMsg =
                            `Totales no coinciden — ` +
                            `Matrícula H=${matriculaH} M=${matriculaM} | ` +
                            `Aprov H=${aprovH} M=${aprovM}`;
                        console.warn(`❌ Semestre ${semestreId}: ${errorMsg}`);
                        semestresConError++;
                        if (resumenItem) {
                            resumenItem.observaciones.push(
                                `Semestre ${semestreId}: ${errorMsg}`
                            );
                        }
                        // NO guardar, NO finalizar → siguiente semestre
                        continue;
                    }

                    // 3. Totales coinciden → guardar y finalizar
                    await guardarSemestreSilencioso(
                        item.programaNombre,
                        item.modalidadNombre,
                        semestreId
                    );
                    await finalizarSemestreSilencioso(
                        item.programaNombre,
                        item.modalidadNombre,
                        semestreId
                    );

                    semestresExitosos++;
                    if (resumenItem) resumenItem.semestresOk++;

                } catch (semError) {
                    console.error(`Error semestre ${semestreId}:`, semError);
                    semestresConError++;
                    if (resumenItem) {
                        resumenItem.observaciones.push(
                            `Semestre ${semestreId}: ${semError.message}`
                        );
                    }
                } finally {
                    // Siempre incrementar, pase lo que pase
                    semestresProcesados++;
                    actualizarModalProgresoCircular(
                        semestresProcesados,
                        totalSemestresPlan,
                        `${item.programaNombre} / ${item.modalidadNombre}`,
                        `${semestresProcesados} de ${totalSemestresPlan} semestres procesados`
                    );
                }
            }
        }

        cerrarModalProgresoCircular();

        // Mostrar resumen final
        const totalProcesados = semestresExitosos + semestresConError;
        const eficiencia = totalSemestresPlan > 0 ? Math.round((semestresExitosos / totalSemestresPlan) * 100) : 0;

        const filasResumen = resumen.map(r => {
            const estado = (r.semestresTotal > 0 && r.semestresOk === (r.semestresTotal - r.semestresCompletos)) 
                ? 'Completado' 
                : (r.semestresOk > 0 ? 'Parcial' : 'Pendiente');
            const obs = r.observaciones.slice(0,2).join('; ') || '-';
            return `<tr>
                <td style="padding:6px;border-bottom:1px solid #eee;">${r.programaNombre}</td>
                <td style="padding:6px;border-bottom:1px solid #eee;">${r.modalidadNombre}</td>
                <td style="padding:6px;border-bottom:1px solid #eee;text-align:center;">${r.semestresOk}/${r.semestresTotal - r.semestresCompletos} (${r.semestresCompletos} ya completos)</td>
                <td style="padding:6px;border-bottom:1px solid #eee;text-align:center;">${r.turnosOk}</td>
                <td style="padding:6px;border-bottom:1px solid #eee;">${estado}</td>
                <td style="padding:6px;border-bottom:1px solid #eee;max-width:260px;">${obs}</td>
            </tr>`;
        }).join('');

        await Swal.fire({
            icon: semestresConError === 0 ? 'success' : 'warning',
            title: 'Resumen de Validación Masiva',
            html: `<div style="text-align:left;">
                <p><strong>Semestres procesados:</strong> ${semestresExitosos} / ${totalSemestresPlan} (${eficiencia}%)</p>
                <p><strong>Semestres ya validados (omitidos):</strong> ${semestresYaCompletos}</p>
                <p><strong>Campos rellenados con cero:</strong> ${turnosRellenados}</p>
                ${semestresConError > 0 ? `<p style="color:#dc3545;"><strong>Semestres con error:</strong> ${semestresConError}</p>` : ''}
                <div style="max-height:260px;overflow:auto;border:1px solid #ddd;border-radius:8px;">
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        <thead><tr><th>Programa</th><th>Modalidad</th><th>Semestres</th><th>Turnos OK</th><th>Estado</th><th>Observaciones</th></tr></thead>
                        <tbody>${filasResumen}</tbody>
                    </table>
                </div>
            </div>`,
            width: '980px',
            confirmButtonText: 'Entendido'
        });

        actualizarColoresPestanas();
        // Mostrar pantalla de carga antes de recargar
        mostrarPantallaCarga("Recargando información...");
        setTimeout(() => {
            window.location.reload();
        }, 500);


    } catch (error) {
        cerrarModalProgresoCircular();
        console.error('Error en validación masiva:', error);
        await Swal.fire({ icon: 'error', title: 'Error', text: error.message || 'Error inesperado' });
    } finally {
        validacionMasivaEnCurso = false;
        // Restaurar filtros originales
        programaSelect.value = estadoOriginal.programa;
        const changeEvent = new Event('change', { bubbles: true });
        programaSelect.dispatchEvent(changeEvent);
        await new Promise(r => setTimeout(r, 300));
        if (Array.from(modalidadSelect.options).some(opt => opt.value === estadoOriginal.modalidad)) {
            modalidadSelect.value = estadoOriginal.modalidad;
        }
        semestreInput.value = estadoOriginal.semestre;
        turnoInput.value = estadoOriginal.turno;
        await window.cargarTablaAprovechamiento(estadoOriginal.programa, estadoOriginal.modalidad, parseInt(estadoOriginal.semestre));
        btnValidarTodos.textContent = estadoOriginal.textoBoton;
        btnValidarTodos.disabled = false;
    }
};
// ==========================================
// Función: Limpiar Formulario (Campos Editables)
// ==========================================
window.limpiarFormulario = function () {
    // 1. Obtener solo los inputs editables que NO sean de solo lectura ni estén deshabilitados
    const inputsEditables = document.querySelectorAll(
        '#tabla-body input.input-matricula-nueva:not([disabled]):not([readonly])'
    );

    // Filtrar explícitamente cualquier input que pertenezca a la fila de 'Inscritos'
    const inputsAFiltrar = Array.from(inputsEditables).filter(input => {
        const tipo = String(input.dataset.tipo || '').toLowerCase();
        return tipo !== 'inscritos';
    });

    if (inputsAFiltrar.length === 0) {
        Swal.fire({
            icon: 'info',
            title: 'Sin campos editables',
            text: 'No hay campos editables disponibles para limpiar en este semestre.',
            confirmButtonText: 'Entendido'
        });
        return;
    }

    // 2. Limpiar los campos a 0 y registrar el cambio en la memoria temporal
    inputsAFiltrar.forEach(input => {
        input.value = 0;

        const key = `${semestreActual}|${input.dataset.tipo}|${input.dataset.turno}|${input.dataset.sexo}`;
        cambiosGlobales[key] = 0;
    });

    // 3. Recalcular dinámicamente las sumas en pantalla
    calcularTablaUnificada();

    // Sincronizar deserción calculada del semestre actual en cambiosGlobales
    document.querySelectorAll('#tabla-body .span-desercion-calculada').forEach(span => {
        const valD = parseInt(span.dataset.valor ?? span.textContent.replace(/,/g, ''), 10) || 0;
        const keyD = `${semestreActual}|Deserción|${span.dataset.turno}|${span.dataset.sexo}`;
        cambiosGlobales[keyD] = valD;
    });

    renderizarSeccionTotales();

    // 4. Notificación visual
    const toast = Swal.mixin({
        toast: true,
        position: 'top',
        showConfirmButton: false,
        timer: 1500,
        timerProgressBar: true
    });
    toast.fire({
        icon: 'success',
        title: 'Campos editables limpiados correctamente'
    });
};

// ==========================================
// 17. Inicialización
// ==========================================
document.addEventListener('DOMContentLoaded', function () {
    const loader          = document.getElementById('pantalla-carga');
    const programaSelect  = document.getElementById('programa');
    const modalidadSelect = document.getElementById('modalidad');

    const ocultarLoader = () => {
        if (loader) { loader.style.opacity = '0'; setTimeout(() => { loader.style.display = 'none'; }, 500); }
    };

    if (!window.aprovechamientos) { console.warn('⚠️ No hay datos en window.aprovechamientos'); ocultarLoader(); return; }

    // Asignar variables de validación desde el backend
    if (typeof window.usuario_ya_valido !== 'undefined') usuario_ya_valido = window.usuario_ya_valido;
    if (typeof window.usuario_ya_rechazo !== 'undefined') usuario_ya_rechazo = window.usuario_ya_rechazo;

    document.addEventListener('click', function (e) {
        const container = document.querySelector('.notificaciones-container');
        if (container && !container.contains(e.target)) {
            const panel = document.getElementById('panel-notificaciones');
            if (panel) panel.style.display = 'none';
        }
    });

    document.addEventListener('input', function (e) {
        if (e.target.classList.contains('input-matricula-nueva')) {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
        }
    });

    function limpiarSeccionTotales() {
        const sec = document.getElementById('seccion-totales-aprovechamiento');
        if (sec) sec.remove();
    }

    function cargarProgramas(estadoGuardado = null) {
        programaSelect.innerHTML = '';
        const progSet  = new Set();
        const opciones = [];
        window.aprovechamientos.forEach(item => {
            if (item.Nombre_Programa && !progSet.has(item.Nombre_Programa)) {
                progSet.add(item.Nombre_Programa);
                const opt = document.createElement('option');
                opt.value = item.Nombre_Programa;
                opt.textContent = item.Nombre_Programa;
                opciones.push(opt);
            }
        });
        programaSelect.append(...opciones);
        if (opciones.length > 0) {
            const progSeleccionado = estadoGuardado?.programa || opciones[0].value;
            programaSelect.value = progSeleccionado;
            cargarModalidades(progSeleccionado, estadoGuardado);
        }
    }

    function cargarModalidades(prog, estadoGuardado = null) {
        modalidadSelect.innerHTML = '';
        const modSet   = new Set();
        const opciones = [];
        const progNorm = String(prog).trim().toUpperCase();
        window.aprovechamientos.forEach(item => {
            const itemProgNorm = String(item.Nombre_Programa || '').trim().toUpperCase();
            if (itemProgNorm === progNorm && item.Modalidad && !modSet.has(item.Modalidad)) {
                modSet.add(item.Modalidad);
                const opt = document.createElement('option');
                opt.value = item.Modalidad;
                opt.textContent = item.Modalidad;
                opciones.push(opt);
            }
        });
        modalidadSelect.append(...opciones);
        if (opciones.length > 0) {
            const modSeleccionado = estadoGuardado?.modalidad || opciones[0].value;
            modalidadSelect.value = modSeleccionado;
            window.cargarSemestresTabs(prog, modSeleccionado, estadoGuardado?.semestre ?? null);
        } else {
            const capturaContainer = document.getElementById('captura-matricula-container');
            if (capturaContainer) capturaContainer.style.display = 'none';
        }
    }

    programaSelect.addEventListener('change', function () {
        semestreActual = 0; cambiosGlobales = {}; estadosSemaforoPorSemestre = {};
        limpiarSeccionTotales();
        cargarModalidades(this.value);
    });

    modalidadSelect.addEventListener('change', function () {
        cambiosGlobales = {}; estadosSemaforoPorSemestre = {};
        limpiarSeccionTotales();
        const prog = document.getElementById('programa')?.value;
        if (prog) window.cargarSemestresTabs(prog, this.value);
    });

    setTimeout(() => {
        try {
            const guardado = JSON.parse(localStorage.getItem('filtro_aprovechamiento'));
            if (guardado) {
                localStorage.removeItem('filtro_aprovechamiento');
                if (guardado.scrollPos) scrollPendiente = parseInt(guardado.scrollPos);
                cargarProgramas(guardado);
            } else {
                cargarProgramas();
            }
        } catch (e) {
            console.error('Error en carga inicial:', e);
            cargarProgramas();
        } finally {
            ocultarLoader();
        }
    }, 100);
});

// Restricción global para inputs de captura numérica (4 dígitos, sin signos ni puntos)
document.addEventListener('keydown', function(e) {
    if (e.target && (e.target.matches('.input-matricula-nueva') || (e.target.type === 'number' && e.target.closest('#tabla-unificada, #tabla-body, .tabla-matricula-container')))) {
        if (['-', '.', '+', 'e', 'E', ','].includes(e.key)) {
            e.preventDefault();
        }
    }
}, true);

document.addEventListener('input', function(e) {
    if (e.target && (e.target.matches('.input-matricula-nueva') || (e.target.type === 'number' && e.target.closest('#tabla-unificada, #tabla-body, .tabla-matricula-container')))) {
        const clean = e.target.value.replace(/[^0-9]/g, '').slice(0, 4);
        if (e.target.value !== clean) {
            e.target.value = clean;
        }
    }
}, true);

document.addEventListener('paste', function(e) {
    if (e.target && (e.target.matches('.input-matricula-nueva') || (e.target.type === 'number' && e.target.closest('#tabla-unificada, #tabla-body, .tabla-matricula-container')))) {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData('text') || '';
        const clean = text.replace(/[^0-9]/g, '').slice(0, 4);
        e.target.value = clean;
        e.target.dispatchEvent(new Event('input', { bubbles: true }));
        e.target.dispatchEvent(new Event('change', { bubbles: true }));
    }
}, true);