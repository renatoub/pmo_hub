document.addEventListener('DOMContentLoaded', function () {
    // Usamos o seletor da tabela do admin
    const resultList = document.querySelector('#result_list');

    if (resultList) {
        resultList.addEventListener('click', function (e) {
            if (e.target.classList.contains('toggle-icon')) {
                // ISSO AQUI É O SEGREDO:
                e.preventDefault();  // Não segue o link de edição
                e.stopPropagation(); // Não propaga para a linha da tabela

                const btn = e.target;
                const container = btn.parentElement.querySelector('.desc-content');

                if (container.style.display === 'none') {
                    container.style.display = 'block';
                    btn.style.transform = 'rotate(90deg)';
                    btn.textContent = '▼'; // Seta para baixo ao abrir
                } else {
                    container.style.display = 'none';
                    btn.style.transform = 'rotate(0deg)';
                    btn.textContent = '▶'; // Seta para o lado ao fechar
                }
            }
        });
    }
});