
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