(function($) {
    $(function() {
        var projectSelect = $('#id_project');
        var assetSelect = $('#id_asset');

        function updateAssets(projectId) {
            if (!projectId) {
                assetSelect.html('<option value="">---------</option>');
                return;
            }

            var url = '/admin/lineage/gcptable/ajax/load-assets/?project_id=' + projectId;
            
            $.getJSON(url, function(data) {
                var options = '<option value="">---------</option>';
                $.each(data, function(index, item) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                });
                assetSelect.html(options);
            });
        }

        projectSelect.change(function() {
            updateAssets($(this).val());
        });
    });
})(django.jQuery);
