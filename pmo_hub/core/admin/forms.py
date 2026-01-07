from django import forms
from django.forms.widgets import FileInput

from ..models import AnexoDemanda, Demanda, Rotulos, Situacao


class MultipleFileInput(FileInput):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs["multiple"] = "multiple"
        return super().render(name, value, attrs, renderer)


class AnexoForm(forms.ModelForm):
    arquivo = forms.FileField(
        widget=MultipleFileInput(), required=False, label="Adicionar arquivo(s)"
    )

    class Meta:
        model = AnexoDemanda
        fields = ["arquivo"]


class SituacaoForm(forms.ModelForm):
    class Meta:
        model = Situacao
        fields = "__all__"
        widgets = {"cor_hex": forms.TextInput(attrs={"type": "color"})}


class RotuloForm(forms.ModelForm):
    class Meta:
        model = Rotulos
        fields = "__all__"
        widgets = {
            "cor_hex": forms.TextInput(
                attrs={"type": "color", "style": "height: 40px; width: 60px;"}
            )
        }


class DemandaForm(forms.ModelForm):
    pendencia_descricao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obrigatório ao marcar como pendente.",
    )

    class Meta:
        model = Demanda
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        situacao = cleaned.get("situacao")
        desc = cleaned.get("pendencia_descricao")
        if situacao and "pend" in situacao.nome.lower():
            if self.instance.situacao_id != situacao.pk and not desc:
                raise forms.ValidationError(
                    {"pendencia_descricao": "Descrição obrigatória para pendências."}
                )
        return cleaned
