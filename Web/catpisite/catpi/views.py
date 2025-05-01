from django.shortcuts import render
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
#from .models import Catpi
from django.conf import settings
#from catpi.forms import AddCatpiForm

class IndexView(LoginRequiredMixin, generic.ListView):
    template_name = 'catpi/index.html'

    def get_queryset(self):
        results = Catpi.objects.filter(user=self.request.user)
        return results
    
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        return context

class DetailView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'catpi/detail.html'

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['device'] = get_object_or_404(
            Lampi, pk=kwargs['device_id'], user=self.request.user)
        return context

class AddCatpiView(LoginRequiredMixin, generic.FormView):
    template_name = 'catpi/addcatpi.html'
   # form_class = AddCatpiForm
    success_url = '/catpi'

    def get_context_data(self, **kwargs):
        context = super(AddCatpiView, self).get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        device = form.cleaned_data['device']
        device.associate_and_publish_associated_msg(self.request.user)

        return super(AddCatpiView, self).form_valid(form)
