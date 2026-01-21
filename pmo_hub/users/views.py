from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileUpdateForm


@login_required
def profile(request):
    if request.method == "POST":
        p_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=request.user.profile
        )
        if p_form.is_valid():
            p_form.save()
            return redirect("profile")
    else:
        p_form = ProfileUpdateForm(instance=request.user.profile)

    return render(request, "users/profile.html", {"p_form": p_form})
