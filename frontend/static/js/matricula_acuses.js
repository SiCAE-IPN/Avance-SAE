async function cargarAcuses() {
    const tbody = document.getElementById('acuses-tbody');
    const empty = document.getElementById('acuses-empty');

    if (!tbody || !empty) {
        return;
    }

    tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">Cargando acuses...</td></tr>';

    try {
        const resp = await fetch('/matricula/acuses/listado');
        const data = await resp.json();

        if (!data.success) {
            throw new Error(data.error || 'No se pudo obtener el listado de acuses');
        }

        const items = data.items || [];
        if (items.length === 0) {
            tbody.innerHTML = '';
            empty.style.display = 'block';
            return;
        }

        empty.style.display = 'none';
        tbody.innerHTML = items
            .map((item) => {
                const size = `${item.size_kb} KB`;
                return `
                    <tr>
                        <td>${item.file_name}</td>
                        <td>${item.created_at_display}</td>
                        <td>${size}</td>
                        <td>
                            <a class="btn-link" href="${item.download_url}" target="_blank" rel="noopener">Abrir PDF</a>
                        </td>
                    </tr>
                `;
            })
            .join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">Error: ${err.message}</td></tr>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btnRecargar = document.getElementById('btn-recargar-acuses');
    if (btnRecargar) {
        btnRecargar.addEventListener('click', cargarAcuses);
    }
    cargarAcuses();
});
