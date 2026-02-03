document.addEventListener('DOMContentLoaded', function () {
    // Usamos delegação de eventos para funcionar mesmo se a tabela mudar
    document.querySelector('#result_list').addEventListener('click', function (e) {
        if (e.target.classList.contains('toggle-desc')) {
            const btn = e.target;
            const container = btn.nextElementSibling; // O div .desc-content

            if (container.style.display === 'none') {
                container.style.display = 'block';
                btn.textContent = '➖';
            } else {
                container.style.display = 'none';
                btn.textContent = '➕';
            }
        }
    });
});