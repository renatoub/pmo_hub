// resolution_content: Script para atualizar o help_text dinamicamente via AJAX
document.addEventListener('DOMContentLoaded', function() {
    const cronInput = document.querySelector('#id_schedule');
    const helpText = document.querySelector('#id_schedule + .help-text, #id_schedule ~ .help');

    if (cronInput) {
        cronInput.addEventListener('input', function() {
            const val = this.value;
            if (val.split(' ').length >= 5) {
                fetch(`/gcp/api/cron-description/?cron=${encodeURIComponent(val)}`)
                    .then(response => response.json())
                    .then(data => {
                        helpText.innerHTML = `<strong>Tradução:</strong> ${data.description}`;
                        helpText.style.color = data.valid ? "#2a9d8f" : "#d62828";
                    });
            }
        });
    }
});
