
function actualizarValorFila(idFila, campo, valor) {

    const numero = valor === "" ? 0 : Math.max(0, Number(valor));

    const fila = filasEgresados.find(f => f.id === idFila);

    if (fila) {
        fila[campo] = numero;
    }

    console.log("Filas actualizadas:", filasEgresados);
}

function guardarAvance() {
    fetch('/titulados/guardar-avance-titulados', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(filasEgresados)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Respuesta del servidor:', data);
        alert('Avance guardado correctamente');
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error al guardar');
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
            fila.Tipo_Titulacion,
            fila.Grupo_Edad
        ].join('|');

        if (!grupos[clave]) {
            grupos[clave] = {
                Nombre_Programa: fila.Nombre_Programa,
                Modalidad:       fila.Modalidad,
                Turno:           fila.Turno,
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

    filas.forEach(fila => {
        const total = fila.Hombres + fila.Mujeres;
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #ddd';
        tr.innerHTML = `
            <td style="padding: 12px; text-align: left;   border: 1px solid #ddd;">${fila.Nombre_Programa}</td>
            <td style="padding: 12px; text-align: left;   border: 1px solid #ddd;">${fila.Modalidad}</td>
            <td style="padding: 12px; text-align: left;   border: 1px solid #ddd;">${fila.Turno}</td>
            <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">2024</td>
            <td style="padding: 12px; text-align: left;   border: 1px solid #ddd;">${fila.Tipo_Titulacion}</td>
            <td style="padding: 12px; text-align: left;   border: 1px solid #ddd;">${fila.Grupo_Edad}</td>
            <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">${fila.Hombres}</td>
            <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">${fila.Mujeres}</td>
            <td style="padding: 12px; text-align: center; border: 1px solid #ddd; font-weight: bold;">${total}</td>
        `;
        tbody.appendChild(tr);
    });
}




