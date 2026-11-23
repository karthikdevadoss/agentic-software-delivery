from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ASD local admin (read-only slice)"
admin.site.index_title = "Ledger / budgets / evals -- local, not the product"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("ledger.urls")),
]
