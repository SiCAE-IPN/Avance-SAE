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
// 4. Pestanas de semestres
// ==========================================
window.cargarSemestresTabs = function (prog, mod, semForzado = null) {
    const container = document.getElementById('semestres-tabs');
    if (!container) return;
    container.innerHTML = '';

    if (!window.aprovechamientos) return;

    procesarEstadosSemaforoAprovechamiento(prog, mod);

    if (semestresDisponiblesSP.length === 0) {
        const tbody = document.getElementById('tabla-body');
        if (tbody) tbody.innerHTML = '';
        return;
    }

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
    row1.style.background = 'linear-gradient(135deg, #6e0343 0%, #8B0A4A 100%)';
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

    const datosInscritos      = mapearDatos(window.inscritos);
    const datosReincorporados = mapearDatos(window.reincorporados);

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

    const listaSit = Object.keys(datosAprovechamiento).length > 0
        ? Object.keys(datosAprovechamiento)
        : ['Aprobado', 'Reprobado', 'Desertor'];

    listaSit.forEach(sit => {
        crearFilaInput(tbody, sit, turnos, datosAprovechamiento[sit] || {}, false, 'fila-aprovechamiento', esSemestreBloqueado);
    });

    crearFilaTotalizador(tbody, 'Total Aprovechamiento', turnos, 'total-aprovechamiento', '#fff3e0');
    calcularTablaUnificada();

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
function crearFilaInput(tbody, titulo, turnos, datosMapa, esSoloLectura, claseFila, esBloqueadoGral) {
    const tr = document.createElement('tr');
    tr.className = claseFila;
    tr.style.borderBottom = '1px solid #e0e0e0';
    tr.style.transition   = 'all 0.2s ease';
    tr.onmouseover = () => tr.style.backgroundColor = '#f5f5f5';
    tr.onmouseout  = () => tr.style.backgroundColor = '';

    let html = `<td style="font-weight:600; padding:14px 12px; border:1px solid #dee2e6; vertical-align:middle; font-size:14px; color:#333; background:#f8f9fa; white-space:normal; word-break:keep-all; min-width:160px; width:160px; max-width:160px;">${titulo}</td>`;

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
                    <input type="number" min="0"
                        class="input-matricula-nueva"
                        data-tipo="${titulo}" data-turno="${t}" data-sexo="Hombre"
                        value="${valH}" oninput="registrarCambio(this)" ${attr}
                        style="width:64px; padding:4px 6px; border:2px solid #2196f3; border-radius:4px; background:${bgH}; color:#1976d2; font-weight:600; text-align:center; font-size:13px;">
                </div>
                <div style="display:inline-flex; align-items:center; gap:4px; padding:4px 8px; background:#fce4ec; border-radius:6px; border:1px solid #f48fb1;">
                    <div style="font-weight:700; color:#c2185b; font-size:12px; min-width:14px; text-align:center;">M</div>
                    <input type="number" min="0"
                        class="input-matricula-nueva"
                        data-tipo="${titulo}" data-turno="${t}" data-sexo="Mujer"
                        value="${valM}" oninput="registrarCambio(this)" ${attr}
                        style="width:64px; padding:4px 6px; border:2px solid #e91e63; border-radius:4px; background:${bgM}; color:#c2185b; font-weight:600; text-align:center; font-size:13px;">
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

    let html = `<td style="text-align:right; padding:14px 12px; font-weight:700; font-size:14px; border:1px solid #dee2e6; color:#333; background:#f8f9fa; white-space:normal; word-break:keep-all; min-width:160px; width:160px; max-width:160px;">${titulo}:</td>`;

    turnos.forEach((t, indexTurno) => {
        const borderRight = indexTurno < turnos.length - 1 ? 'border-right:3px solid #8B0A4A;' : '';
        html += `
        <td style="text-align:center; border:1px solid #dee2e6; ${borderRight} padding:12px 8px;">
            <div style="display:inline-flex; gap:10px; justify-content:center; align-items:center;">
                <div style="display:inline-flex; align-items:center; gap:6px; padding:6px 14px; background:#e3f2fd; border-radius:8px; border:2px solid #90caf9;">
                    <span style="font-size:14px; color:#1976d2; font-weight:800;">H</span>
                    <span id="${idBase}-${t}-Hombre" style="font-weight:800; color:#1976d2; font-size:26px; min-width:28px; display:inline-block; text-align:center; line-height:1;">0</span>
                </div>
                <div style="display:inline-flex; align-items:center; gap:6px; padding:6px 14px; background:#fce4ec; border-radius:8px; border:2px solid #f48fb1;">
                    <span style="font-size:14px; color:#c2185b; font-weight:800;">M</span>
                    <span id="${idBase}-${t}-Mujer" style="font-weight:800; color:#c2185b; font-size:26px; min-width:28px; display:inline-block; text-align:center; line-height:1;">0</span>
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
    const key = `${semestreActual}|${input.dataset.tipo}|${input.dataset.turno}|${input.dataset.sexo}`;
    cambiosGlobales[key] = input.value === '' ? '' : parseInt(input.value);
    calcularTablaUnificada();
    renderizarSeccionTotales();
};

window.calcularTablaUnificada = function () {
    const sumaMatricula = {};
    document.querySelectorAll('.fila-matricula input').forEach(input => {
        const key = `${input.dataset.turno}-${input.dataset.sexo}`;
        sumaMatricula[key] = (sumaMatricula[key] || 0) + (parseInt(input.value) || 0);
    });
    Object.entries(sumaMatricula).forEach(([key, val]) => {
        const span = document.getElementById(`total-matricula-${key}`);
        if (span) span.textContent = val;
    });

    const sumaAprov = {};
    document.querySelectorAll('.fila-aprovechamiento input').forEach(input => {
        const key = `${input.dataset.turno}-${input.dataset.sexo}`;
        sumaAprov[key] = (sumaAprov[key] || 0) + (parseInt(input.value) || 0);
    });

    if (window.turnosActualesPantalla) {
        window.turnosActualesPantalla.forEach(t => {
            ['Hombre', 'Mujer'].forEach(s => {
                const key  = `${t}-${s}`;
                const span = document.getElementById(`total-aprovechamiento-${key}`);
                if (!span) return;
                const totalM = sumaMatricula[key] || 0;
                const totalA = sumaAprov[key]     || 0;
                if (totalM !== totalA) {
                    span.style.color = '#dc3545';
                    span.innerHTML   = `${totalA} <i class="fas fa-exclamation-circle" style="font-size:16px;"></i>`;
                } else {
                    span.style.color = '#198754';
                    span.innerHTML   = `${totalA} <i class="fas fa-check" style="font-size:16px;"></i>`;
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
// 11. TOTALES + TABLA RESUMEN + SEMÁFORO
// ==========================================
function obtenerTotalesAprovechamiento() {
    let totalH = 0, totalM = 0;
    const porConcepto = {};

    document.querySelectorAll('.fila-aprovechamiento input').forEach(input => {
        const val      = parseInt(input.value) || 0;
        const concepto = input.dataset.tipo || 'Sin especificar';
        const sexo     = input.dataset.sexo;

        if (!porConcepto[concepto]) porConcepto[concepto] = { H: 0, M: 0 };
        if (sexo === 'Hombre') { totalH += val; porConcepto[concepto].H += val; }
        else if (sexo === 'Mujer') { totalM += val; porConcepto[concepto].M += val; }
    });

    return { totalH, totalM, porConcepto };
}

// Construye el HTML del panel semáforo con TODOS los programas/modalidades de la escuela

function buildResumenSemaforo() {
    if (!window.aprovechamientos || window.aprovechamientos.length === 0) return '';

    const cfg = {
        1: { bar:'#e24b4a', bg:'rgba(226,75,74,.07)',  dot:'#e24b4a', label:'Sin datos', textColor:'#a32d2d' },
        2: { bar:'#ef9f27', bg:'rgba(239,159,39,.08)', dot:'#ef9f27', label:'Parcial',   textColor:'#854f0b' },
        3: { bar:'#639922', bg:'rgba(99,153,34,.07)',  dot:'#639922', label:'Completo',  textColor:'#3b6d11' },
    };

    // Agrupar: { "PROG||MOD": { prog, mod, sems: { numSem: idSemaforo } } }
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

    // Contadores globales
    const totales = { 1:0, 2:0, 3:0 };
    Object.values(grupos).forEach(g =>
        Object.values(g.sems).forEach(id => totales[id] = (totales[id]||0)+1)
    );

    // Ordenar grupos alfabéticamente por programa
    const gruposOrdenados = Object.entries(grupos)
        .sort(([, a], [, b]) => a.prog.localeCompare(b.prog, 'es'));

    const bloques = gruposOrdenados.map(([key, g]) => {
        const esActivo = key === `${progActual}||${modActual}`;
        const semestresList = Object.keys(g.sems).map(Number).sort((a,b)=>a-b);

        // Tarjetas mini por semestre
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
            ? 'border:2px solid #6e0343; box-shadow:0 0 0 3px rgba(110,3,67,.1);'
            : 'border:1px solid #e8e8e8;';

        const badgeActivo = esActivo
            ? `<span style="font-size:10px;padding:2px 8px;border-radius:100px;background:#6e0343;color:white;font-weight:600;flex-shrink:0;">Activo</span>`
            : '';

        // Nombre corto del programa
        const shortProg = g.prog.length > 45 ? g.prog.slice(0,43)+'…' : g.prog;

        return `
        <div style="background:white;border-radius:10px;${bordeActivo} padding:12px 14px;">
            <!-- Encabezado del bloque -->
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:10px;">
                <div style="min-width:0;">
                    <div style="font-size:12px;font-weight:600;color:#333;line-height:1.3;margin-bottom:2px;" title="${g.prog}">${shortProg}</div>
                    <div style="font-size:11px;color:#888;">${g.mod}</div>
                </div>
                ${badgeActivo}
            </div>
            <!-- Grid de semestres -->
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(72px,1fr));gap:6px;">
                ${tarjetas}
            </div>
        </div>`;
    }).join('');

    return `
    <div style="margin-top:28px;background:white;border-radius:14px;box-shadow:0 4px 20px rgba(0,0,0,.08);overflow:hidden;">

        <!-- Encabezado -->
        <div style="background:linear-gradient(135deg,#6e0343,#8B0A4A);padding:14px 20px;
                    display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
            <span style="color:white;font-size:16px;font-weight:700;">📋 Estado de captura — todos los programas</span>
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
                <span style="font-size:11px;padding:3px 10px;border-radius:100px;background:rgba(226,75,74,.3);color:#ffcfcf;font-weight:600;">Sin datos: ${totales[1]}</span>
                <span style="font-size:11px;padding:3px 10px;border-radius:100px;background:rgba(239,159,39,.3);color:#ffe8b0;font-weight:600;">Parcial: ${totales[2]}</span>
                <span style="font-size:11px;padding:3px 10px;border-radius:100px;background:rgba(99,153,34,.3);color:#d0edaa;font-weight:600;">Completo: ${totales[3]}</span>
            </div>
        </div>

        <!-- Leyenda -->
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

        <!-- Grid de programas -->
        <div style="padding:16px 20px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;">
            ${bloques}
        </div>

    </div>`;
}

// Navega a un programa/modalidad/semestre específico desde el panel global
function irASemestreGlobal(prog, mod, sem) {
    const programaSelect  = document.getElementById('programa');
    const modalidadSelect = document.getElementById('modalidad');
    if (!programaSelect || !modalidadSelect) return;

    // Si el programa ya está en el select, seleccionarlo directamente
    const optProg = Array.from(programaSelect.options).find(o => o.value === prog);
    if (optProg) {
        programaSelect.value = prog;
        // Recargar modalidades y luego seleccionar semestre
        cambiosGlobales = {}; estadosSemaforoPorSemestre = {};
        const secTot = document.getElementById('seccion-totales-aprovechamiento');
        if (secTot) secTot.remove();

        // Poblar modalidades para el nuevo programa
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

        // Scroll suave a la tabla tras breve espera
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
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#333; font-weight:500;">${concepto}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#1565c0; font-weight:700;">${H.toLocaleString()}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#ad1457; font-weight:700;">${M.toLocaleString()}</td>
                <td style="padding:12px 20px; border:1px solid #e0e0e0; text-align:center; font-size:15px; color:#6e0343; font-weight:800;">${total.toLocaleString()}</td>
            </tr>`;
        }).join('')
        : `<tr><td colspan="4" style="padding:24px; text-align:center; color:#999; font-style:italic; font-size:14px;">Sin datos capturados aún</td></tr>`;

    contenedor.innerHTML = `

        <!-- ── Barra de Totales Generales ── -->
        
        <!-- ── Tabla Resumen ── -->
        <div style="background:white; border-radius:14px; box-shadow:0 4px 20px rgba(0,0,0,.08); overflow:hidden;">
            <div style="background:linear-gradient(135deg,#6e0343,#8B0A4A); color:white; 
                padding:16px 24px; font-size:20px; text-align:center; font-weight:700; letter-spacing:.3px;">
                📊 Resumen de Aprovechamiento — Semestre ${semestreActual}
            </div>
            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:collapse;">
                    <thead>
                        <tr>
                            <th style="padding:14px 20px; text-align:center; font-size:20px; font-weight:700;
                                background:linear-gradient(135deg,#6e0343,#8B0A4A); color:white;
                                border:1px solid rgba(255,255,255,.2);">Situación Académica</th>
                            <th style="padding:14px 20px; text-align:center; font-size:20px; font-weight:700;
                                background:#1565c0; color:white; border:1px solid rgba(255,255,255,.2);">Hombres</th>
                            <th style="padding:14px 20px; text-align:center; font-size:20px; font-weight:700;
                                background:#ad1457; color:white; border:1px solid rgba(255,255,255,.2);">Mujeres</th>
                            <th style="padding:14px 20px; text-align:center; font-size:20px; font-weight:700;
                                background:linear-gradient(135deg,#6e0343,#8B0A4A); color:white;
                                border:1px solid rgba(255,255,255,.2);">Total</th>
                        </tr>
                    </thead>
                    <tbody>${filasHTML}</tbody>
                    <tfoot>
                        <tr>
                            <td style="padding:14px 20px; text-align:center; font-weight:800; font-size:15px;
                                background:linear-gradient(135deg,#6e0343,#8B0A4A); color:white;
                                border:1px solid rgba(255,255,255,.2);">TOTAL</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px;
                                background:rgba(21,101,192,.85); color:white;
                                border:1px solid rgba(255,255,255,.2);">${totalH.toLocaleString()}</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px;
                                background:rgba(173,20,87,.85); color:white;
                                border:1px solid rgba(255,255,255,.2);">${totalM.toLocaleString()}</td>
                            <td style="padding:14px 20px; text-align:center; font-weight:900; font-size:20px;
                                background:linear-gradient(135deg,#6e0343,#8B0A4A); color:white;
                                border:1px solid rgba(255,255,255,.2);">${totalGeneral.toLocaleString()}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <!-- ── Panel Semáforo de Semestres ── -->
        
        ${buildResumenSemaforo()}
    `;
}

// ==========================================
// 12. Bloqueo por Semáforo
// ==========================================
function aplicarBloqueoPorSemaforo() {
    const estado     = estadosSemaforoPorSemestre[semestreActual] ?? 1;
    const bloqueado  = (estado === 3);
    const btnGuardar = document.getElementById('btn-guardar-matricula');
    const btnValidar = document.getElementById('btn-validar-matricula');

    if (bloqueado) {
        deshabilitarTodaLaVista();
        if (btnGuardar) { btnGuardar.disabled = true;  btnGuardar.style.display = 'none'; }
        if (btnValidar) { btnValidar.disabled = true;  btnValidar.textContent   = '✅ Semestre Validado'; }
    } else {
        if (btnGuardar) { btnGuardar.disabled = false; btnGuardar.style.display = 'inline-block'; }
        if (btnValidar) { btnValidar.disabled = false; btnValidar.textContent   = '✅ Finalizar Captura'; }
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
            const rProg  = String(r.Nombre_Programa || '').trim().toUpperCase();
            const rMod   = String(r.Modalidad || '').trim().toUpperCase();
            const rSem   = normalizarSemestre(r.Semestre || r.semestre);
            const rSit   = r.Aprovechamiento || r.aprovechamiento || r.Situacion || r.situacion;
            const rTurno = r.Turno || r.turno;
            const rSexo  = r.Sexo  || r.sexo;
            return rProg === progVal && rMod === modVal && rSem === semNum &&
                   rSit  === dato.situacion_academica && rTurno === dato.turno &&
                   String(rSexo).charAt(0) === String(dato.sexo).charAt(0);
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
        const r = await Swal.fire({ title: '⚠️ Totales no coinciden', text: '¿Deseas guardar de todos modos?', icon: 'warning', showCancelButton: true, confirmButtonText: 'Si, guardar' });
        if (!r.isConfirmed) return;
    }
    const claves = Object.keys(cambiosGlobales);
    if (claves.length === 0) { Swal.fire('Informacion', 'No hay cambios pendientes.', 'info'); return; }

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
        const r = await Swal.fire({ title: '⚠️ Error en Totales', text: '¿Forzar validacion con errores?', icon: 'error', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Si, forzar' });
        if (!r.isConfirmed) return;
    }

    const programaVal   = document.getElementById('programa')?.value.trim();
    const modalidadVal  = document.getElementById('modalidad')?.value.trim();
    const semestreTexto = semestreNumeroATexto(semestreActual);

    if (!programaVal || !modalidadVal) { Swal.fire('Error', 'Selecciona Programa y Modalidad', 'error'); return; }

    const confirmResult = await Swal.fire({
        title: `¿Finalizar ${semestreTexto} Semestre?`,
        html: `Estas a punto de validar:<br><b>Programa:</b> ${programaVal}<br><b>Modalidad:</b> ${modalidadVal}<br>
               <b>Semestre:</b> <span style="color:#d33; font-weight:bold;">${semestreTexto}</span><br><br>
               El semaforo cambiara a <b>VERDE</b> y la edicion se bloqueara.`,
        icon: 'question', showCancelButton: true, confirmButtonColor: '#198754', confirmButtonText: 'Si, Finalizar'
    });
    if (!confirmResult.isConfirmed) return;

    Swal.fire({ title: 'Validando...', html: 'Recopilando toda la informacion...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

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
// 15. Validar / Rechazar (Roles Validadores)
// ==========================================
window.validarSemestre = async function () {
    const btnValidar = document.getElementById('btn-validar-semestre');
    if (btnValidar?.disabled) {
        Swal.fire({ icon: 'warning', title: 'Accion no permitida', text: 'Ya has validado o rechazado este aprovechamiento.', confirmButtonText: 'Entendido' });
        return;
    }
    const programaVal   = document.getElementById('programa')?.value.trim();
    const modalidadVal  = document.getElementById('modalidad')?.value.trim();
    const semestreTexto = semestreNumeroATexto(semestreActual);
    const periodoVal    = document.getElementById('periodo-texto')?.textContent.trim() || '';

    if (!programaVal || !modalidadVal) { Swal.fire('Error', 'Selecciona Programa y Modalidad', 'error'); return; }

    const confirmResult = await Swal.fire({
        title: '✅ ¿Validar Aprovechamiento?',
        html: `Estas a punto de <b>validar</b>:<br><b>Programa:</b> ${programaVal}<br>
               <b>Modalidad:</b> ${modalidadVal}<br>
               <b>Semestre:</b> <span style="color:#198754; font-weight:bold;">${semestreTexto}</span>`,
        icon: 'question', showCancelButton: true,
        confirmButtonColor: '#198754', cancelButtonText: 'Cancelar', confirmButtonText: '✅ Si, Validar'
    });
    if (!confirmResult.isConfirmed) return;

    Swal.fire({ title: 'Procesando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

    try {
        const res = await fetch('/aprovechamiento/validar_semestre', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ programa: programaVal, modalidad: modalidadVal, semestre: semestreTexto, periodo: periodoVal, accion: 'validar' })
        });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Error al validar'); }
        await Swal.fire({ title: '¡Aprovechamiento Validado!', text: 'El semestre ha sido validado correctamente.', icon: 'success', timer: 1800, showConfirmButton: false });
        guardarEstadoYRecargar();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

window.rechazarSemestre = function () { abrirPanelRechazo(); };

window.confirmarRechazoPanel = async function () {
    const motivo = document.getElementById('motivo-rechazo-panel')?.value.trim();
    if (!motivo || motivo.length < 10) { Swal.fire('Atencion', 'El motivo de rechazo debe tener al menos 10 caracteres.', 'warning'); return; }

    const programaVal   = document.getElementById('programa')?.value.trim();
    const modalidadVal  = document.getElementById('modalidad')?.value.trim();
    const semestreTexto = semestreNumeroATexto(semestreActual);
    const periodoVal    = document.getElementById('periodo-texto')?.textContent.trim() || '';

    if (!programaVal || !modalidadVal) { Swal.fire('Error', 'Selecciona Programa y Modalidad', 'error'); return; }

    const confirmResult = await Swal.fire({
        title: '❌ ¿Confirmar Rechazo?',
        html: `Se rechazara el aprovechamiento con el siguiente motivo:<br><br>
               <blockquote style="background:#fff3cd; padding:10px; border-left:4px solid #ffc107; text-align:left; border-radius:4px;">"${motivo}"</blockquote>
               Los datos seran devueltos al capturista para su correccion.`,
        icon: 'warning', showCancelButton: true,
        confirmButtonColor: '#d33', cancelButtonText: 'Cancelar', confirmButtonText: '❌ Si, Rechazar'
    });
    if (!confirmResult.isConfirmed) return;

    cerrarPanelRechazo();
    Swal.fire({ title: 'Procesando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

    try {
        const res = await fetch('/aprovechamiento/rechazar_semestre', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ programa: programaVal, modalidad: modalidadVal, semestre: semestreTexto, periodo: periodoVal, motivo, accion: 'rechazar' })
        });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Error al rechazar'); }
        await Swal.fire({ title: '❌ Aprovechamiento Rechazado', text: 'El capturista ha sido notificado para realizar las correcciones.', icon: 'error', timer: 2000, showConfirmButton: false });
        guardarEstadoYRecargar();
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

    panel.style.display = 'block';
    setTimeout(() => panel.classList.add('panel-abierto'), 10);
    setTimeout(() => { if (textarea) textarea.focus(); }, 300);
    setTimeout(() => panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 350);
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
    else { contador.style.color = '#666'; contador.style.fontWeight = 'normal'; }
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
            programaSelect.value = estadoGuardado?.programa || opciones[0].value;
            cargarModalidades(programaSelect.value, estadoGuardado);
        }
    }

    function cargarModalidades(prog, estadoGuardado = null) {
        modalidadSelect.innerHTML = '';
        const modSet   = new Set();
        const opciones = [];
        window.aprovechamientos.forEach(item => {
            if (item.Nombre_Programa === prog && item.Modalidad && !modSet.has(item.Modalidad)) {
                modSet.add(item.Modalidad);
                const opt = document.createElement('option');
                opt.value = item.Modalidad;
                opt.textContent = item.Modalidad;
                opciones.push(opt);
            }
        });
        modalidadSelect.append(...opciones);
        if (opciones.length > 0) {
            modalidadSelect.value = estadoGuardado?.modalidad || opciones[0].value;
            window.cargarSemestresTabs(prog, modalidadSelect.value, estadoGuardado?.semestre ?? null);
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
        window.cargarSemestresTabs(programaSelect.value, this.value);
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